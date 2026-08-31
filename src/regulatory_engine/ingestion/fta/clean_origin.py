from pathlib import Path
import argparse
import re

import pandas as pd

from regulatory_engine.fta.config import (
    load_fta_config,
    get_agreement_config,
)
from regulatory_engine.infrastructure.storage import (
    ensure_local_file,
    persist_file,
    restore_cached_file,
)


def normalize_text(value):
    if value is None:
        return ""

    return " ".join(
        str(value).split()
    ).strip()


def normalize_hs_code(value):
    value = normalize_text(
        value
    )

    if not value:
        return None

    # Example:
    # "85 44" -> "8544"
    value = value.replace(
        " ",
        "",
    )

    # Current runtime lookup uses
    # exact 4-digit HS headings.
    if not re.fullmatch(
        r"\d{4}",
        value,
    ):
        return None

    return value


def extract_percentage(
    rule_text,
):
    if not rule_text:
        return None

    match = re.search(
        r"(\d+(?:[,.]\d+)?)\s*%",
        rule_text,
    )

    if not match:
        return None

    return float(
        match.group(1).replace(
            ",",
            ".",
        )
    )


def extract_value_basis(
    rule_text,
):
    if not rule_text:
        return None

    normalized = (
        rule_text.lower()
    )

    if (
        "prix départ usine"
        in normalized
    ):
        return "prix départ usine"

    return None


def append_text(
    existing,
    addition,
):
    """
    Append text from a continuation row.

    Example:

        8542 | ... | Fabrication...
             |     | dans la limite...

    becomes one logical rule.
    """

    existing = normalize_text(
        existing
    )

    addition = normalize_text(
        addition
    )

    if not addition:
        return existing

    if not existing:
        return addition

    return (
        f"{existing} {addition}"
    )


def read_origin_table(
    input_path: Path,
):
    """
    Read a Textract CSV and normalize it
    into the four logical origin-rule columns.
    """

    # ----------------------------------------
    # Restore the raw Textract CSV from S3
    # if it is missing locally.
    # ----------------------------------------

    input_path = ensure_local_file(
        Path(input_path)
    )

    df = pd.read_csv(
        input_path,
        dtype=str,
        keep_default_na=False,
        header=None,
    )

    if len(df.columns) < 3:
        raise ValueError(
            "Expected at least 3 columns, "
            f"got {len(df.columns)}"
        )

    while len(df.columns) < 4:
        df[len(df.columns)] = ""

    df = df.iloc[
        :,
        :4,
    ]

    df.columns = [
        "hs_code",
        "description",
        "rule_text",
        "alternative_rule_text",
    ]

    return df


def build_logical_rows(
    df,
):
    """
    Convert physical Textract rows into
    logical origin-rule rows.

    Continuation rows with an empty HS-code
    column are attached to the previous
    valid HS4 row.
    """

    logical_rows = []

    current_row = None

    for row in df.itertuples(
        index=False
    ):

        raw_hs_code = normalize_text(
            row.hs_code
        )

        hs_code = normalize_hs_code(
            raw_hs_code
        )

        description = normalize_text(
            row.description
        )

        rule_text = normalize_text(
            row.rule_text
        )

        alternative_rule_text = (
            normalize_text(
                row.alternative_rule_text
            )
        )

        # ----------------------------------
        # New valid HS4 row
        # ----------------------------------

        if hs_code is not None:

            current_row = {
                "hs_code":
                    hs_code,

                "description":
                    description,

                "rule_text":
                    rule_text,

                "alternative_rule_text":
                    alternative_rule_text,
            }

            logical_rows.append(
                current_row
            )

            continue

        # ----------------------------------
        # Continuation row
        # ----------------------------------

        if (
            not raw_hs_code
            and current_row is not None
        ):

            current_row[
                "description"
            ] = append_text(
                current_row[
                    "description"
                ],
                description,
            )

            current_row[
                "rule_text"
            ] = append_text(
                current_row[
                    "rule_text"
                ],
                rule_text,
            )

            current_row[
                "alternative_rule_text"
            ] = append_text(
                current_row[
                    "alternative_rule_text"
                ],
                alternative_rule_text,
            )

            continue

        # ----------------------------------
        # Unsupported non-empty HS values
        #
        # Examples:
        # (1)
        # 8601 à 8607
        #
        # Prevent subsequent continuation
        # rows from attaching to the previous
        # valid HS4 heading.
        # ----------------------------------

        if raw_hs_code:
            current_row = None

    return logical_rows


def clean_logical_rows(
    logical_rows,
    config: dict,
    page_number: int,
):
    """
    Convert logical rows into the common
    fta_origin_rules structure.
    """

    origin_config = config[
        "origin"
    ]

    cleaned_rows = []

    for row in logical_rows:

        rule_text = normalize_text(
            row[
                "rule_text"
            ]
        )

        alternative_rule_text = (
            normalize_text(
                row[
                    "alternative_rule_text"
                ]
            )
        )

        # If Textract placed the only rule
        # in column (4), use it.
        if (
            not rule_text
            and alternative_rule_text
        ):
            rule_text = (
                alternative_rule_text
            )

        if not rule_text:
            continue

        source_excerpt_parts = [
            row[
                "hs_code"
            ],
            row[
                "description"
            ],
            rule_text,
        ]

        if alternative_rule_text:
            source_excerpt_parts.append(
                (
                    "Alternative: "
                    f"{alternative_rule_text}"
                )
            )

        source_excerpt = " | ".join(
            source_excerpt_parts
        )

        cleaned_rows.append(
            {
                "agreement_code":
                    config[
                        "agreement_code"
                    ],

                "exporter_country":
                    config[
                        "exporter_country"
                    ],

                "importer_region":
                    config[
                        "importer_region"
                    ],

                "hs_code":
                    row[
                        "hs_code"
                    ],

                "description":
                    row[
                        "description"
                    ],

                "rule_text":
                    rule_text,

                "max_non_originating_material_pct":
                    extract_percentage(
                        rule_text
                    ),

                "value_basis":
                    extract_value_basis(
                        rule_text
                    ),

                "source_document":
                    config[
                        "source_document"
                    ],

                "source_section":
                    origin_config[
                        "source_section"
                    ],

                "source_page":
                    page_number,

                "source_excerpt":
                    source_excerpt,
            }
        )

    return cleaned_rows


def clean_origin_page(
    config: dict,
    page_number: int,
):
    """
    Clean one configured origin-rule page.
    """

    origin_config = config[
        "origin"
    ]

    input_path = (
        Path(
            origin_config[
                "raw_dir"
            ]
        )
        / f"page-{page_number}.csv"
    )

    output_path = (
        Path(
            origin_config[
                "clean_dir"
            ]
        )
        / f"page-{page_number}.csv"
    )

    # ----------------------------------------
    # Reuse cleaned page if it exists
    # locally or can be restored from S3.
    # ----------------------------------------

    if restore_cached_file(
        output_path
    ):
        print(
            f"Using cached cleaned "
            f"FTA origin page: "
            f"{output_path}"
        )

        return output_path

    # ----------------------------------------
    # read_origin_table() will restore
    # the raw extracted CSV from S3
    # if necessary.
    # ----------------------------------------

    df = read_origin_table(
        input_path
    )

    logical_rows = (
        build_logical_rows(
            df
        )
    )

    cleaned_rows = (
        clean_logical_rows(
            logical_rows=logical_rows,
            config=config,
            page_number=page_number,
        )
    )

    result = pd.DataFrame(
        cleaned_rows
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result.to_csv(
        output_path,
        index=False,
    )

    print(
        f"Cleaned {len(result)} "
        f"origin rules"
    )

    print(
        f"Saved: {output_path}"
    )

    # ----------------------------------------
    # Persist reusable cleaned output to S3.
    #
    # data/cleaned/...
    # →
    # processed/cleaned/...
    # ----------------------------------------

    persist_file(
        output_path
    )

    if not result.empty:

        print()

        print(
            result[
                [
                    "hs_code",
                    "description",
                    "max_non_originating_material_pct",
                    "value_basis",
                ]
            ].to_string(
                index=False
            )
        )

    return output_path


def clean_agreement(
    agreement_key: str,
):
    """
    Clean all configured origin pages for
    one agreement.
    """

    config = get_agreement_config(
        agreement_key
    )

    origin_config = config[
        "origin"
    ]

    page_numbers = origin_config[
        "pages"
    ]

    print(
        f"\nCleaning FTA origin rules: "
        f"{agreement_key}"
    )

    print(
        f"Pages: {page_numbers}"
    )

    output_paths = []

    for page_number in page_numbers:

        output_path = (
            clean_origin_page(
                config=config,
                page_number=page_number,
            )
        )

        output_paths.append(
            output_path
        )

    return output_paths


def main():

    fta_config = load_fta_config()

    parser = argparse.ArgumentParser(
        description=(
            "Clean extracted FTA "
            "origin-rule tables."
        )
    )

    parser.add_argument(
        "agreement",
        choices=[
            *fta_config.keys(),
            "all",
        ],
    )

    args = parser.parse_args()

    if args.agreement == "all":

        for agreement_key in (
            fta_config.keys()
        ):
            clean_agreement(
                agreement_key
            )

    else:

        clean_agreement(
            args.agreement
        )


if __name__ == "__main__":
    main()
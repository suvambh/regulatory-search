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

    text = " ".join(
        str(value).split()
    ).strip()

    text = re.sub(
        r"(?<=\w)-\s+(?=\w)",
        "",
        text,
    )

    return text


def normalize_tariff_code(value):
    """
    Normalize tariff codes:

        8528       -> 8528
        8528 59    -> 852859
        8528 59 90 -> 85285990
    """

    value = normalize_text(
        value
    )

    if not value:
        return None

    value = value.replace(
        " ",
        "",
    )

    if not value.isdigit():
        return None

    if len(value) not in {
        4,
        6,
        8,
    }:
        return None

    return value


def parse_rate(
    value,
):
    value = normalize_text(
        value
    )

    if not value:
        return None

    normalized = value.lower()

    if normalized == "exemption":
        return 0.0

    match = re.search(
        r"(\d+(?:[,.]\d+)?)",
        value,
    )

    if not match:
        return None

    return float(
        match.group(1).replace(
            ",",
            ".",
        )
    )


def append_unique(
    values,
    value,
):
    value = normalize_text(
        value
    )

    if not value:
        return

    if (
        not values
        or values[-1] != value
    ):
        values.append(
            value
        )


def build_description(
    *parts,
):
    """
    Build one searchable description from
    all applicable hierarchy levels.
    """

    result = []

    for part in parts:

        if isinstance(
            part,
            list,
        ):
            values = part
        else:
            values = [
                part
            ]

        for value in values:

            value = normalize_text(
                value
            )

            if not value:
                continue

            if value in result:
                continue

            result.append(
                value
            )

    return " — ".join(
        result
    )


def read_tariff_pages(
    raw_dir: Path,
    page_numbers: list[int],
):
    """
    Read all configured tariff pages as one
    continuous ordered row stream.

    This is important because hierarchy can
    continue from one PDF page to the next.
    """

    rows = []

    for page_number in page_numbers:

        input_path = (
            raw_dir
            / f"page-{page_number}.csv"
        )

        # Restore raw Textract output from S3
        # if it is not present locally.
        input_path = ensure_local_file(
            input_path
        )

        df = pd.read_csv(
            input_path,
            dtype=str,
            keep_default_na=False,
            header=None,
        )

        if len(df.columns) < 4:
            raise ValueError(
                f"Expected at least 4 columns "
                f"in {input_path}, got "
                f"{len(df.columns)}"
            )

        while len(df.columns) < 5:
            df[len(df.columns)] = ""

        df = df.iloc[
            :,
            :5,
        ]

        df.columns = [
            "tariff_code",
            "description",
            "base_rate_text",
            "tariff_category",
            "entry_price_text",
        ]

        for row in df.itertuples(
            index=False
        ):

            raw_code = normalize_text(
                row.tariff_code
            )

            # Skip table header.
            if raw_code.lower() in {
                "nc2007",
                "code",
            }:
                continue

            rows.append(
                {
                    "page":
                        page_number,

                    "raw_code":
                        raw_code,

                    "tariff_code":
                        normalize_tariff_code(
                            raw_code
                        ),

                    "description":
                        normalize_text(
                            row.description
                        ),

                    "base_rate_text":
                        normalize_text(
                            row.base_rate_text
                        ),

                    "tariff_category":
                        normalize_text(
                            row.tariff_category
                        ),

                    "entry_price_text":
                        normalize_text(
                            row.entry_price_text
                        ),
                }
            )

    return rows


def apply_pending_context(
    pending_context,
    previous_code,
    next_code,
    branch_context,
    subheading_context,
):
    """
    Decide where blank-code hierarchy rows
    belong by looking at the next coded row.
    """

    if not pending_context:
        return (
            branch_context,
            subheading_context,
        )

    if not next_code:
        return (
            branch_context,
            subheading_context,
        )

    if len(next_code) == 4:
        return (
            [],
            [],
        )

    previous_hs4 = (
        previous_code[:4]
        if previous_code
        and len(previous_code) >= 4
        else None
    )

    next_hs4 = next_code[
        :4
    ]

    if (
        previous_hs4
        and previous_hs4 != next_hs4
    ):
        return (
            [],
            [],
        )

    previous_hs6 = (
        previous_code[:6]
        if previous_code
        and len(previous_code) >= 6
        else None
    )

    next_hs6 = (
        next_code[:6]
        if len(next_code) >= 6
        else None
    )

    if (
        previous_hs6
        and next_hs6
        and previous_hs6 != next_hs6
    ):
        return (
            list(
                pending_context
            ),
            [],
        )

    if (
        previous_code
        and len(previous_code) == 4
    ):
        return (
            list(
                pending_context
            ),
            [],
        )

    new_subheading_context = list(
        subheading_context
    )

    for value in pending_context:
        append_unique(
            new_subheading_context,
            value,
        )

    return (
        branch_context,
        new_subheading_context,
    )


def clean_tariff_rows(
    rows,
    config,
):
    tariff_config = config[
        "tariff_schedule"
    ]

    cleaned_rows = []

    heading_4_code = None
    heading_4_description = ""

    heading_6_code = None
    heading_6_description = ""

    branch_context = []
    subheading_context = []

    pending_context = []

    previous_code = None

    for row in rows:

        code = row[
            "tariff_code"
        ]

        description = row[
            "description"
        ]

        # ----------------------------------
        # Blank-code hierarchy row
        # ----------------------------------

        if code is None:

            if description:
                pending_context.append(
                    description
                )

            continue

        # ----------------------------------
        # Apply hierarchy labels collected
        # before this coded row.
        # ----------------------------------

        (
            branch_context,
            subheading_context,
        ) = apply_pending_context(
            pending_context=(
                pending_context
            ),
            previous_code=(
                previous_code
            ),
            next_code=code,
            branch_context=(
                branch_context
            ),
            subheading_context=(
                subheading_context
            ),
        )

        pending_context = []

        # ----------------------------------
        # HS4
        # ----------------------------------

        if len(code) == 4:

            heading_4_code = code
            heading_4_description = (
                description
            )

            heading_6_code = None
            heading_6_description = ""

            branch_context = []
            subheading_context = []

            previous_code = code

            continue

        if not heading_4_code:
            previous_code = code
            continue

        # ----------------------------------
        # HS6
        # ----------------------------------

        if len(code) == 6:

            heading_6_code = code
            heading_6_description = (
                description
            )

            subheading_context = []

            previous_code = code

            continue

        # ----------------------------------
        # Leaf tariff line
        # ----------------------------------

        if len(code) != 8:
            previous_code = code
            continue

        hs4_code = code[
            :4
        ]

        effective_heading_6_code = (
            code[
                :6
            ]
        )

        effective_heading_6_description = ""

        if (
            heading_6_code
            == effective_heading_6_code
        ):
            effective_heading_6_description = (
                heading_6_description
            )

        full_description = (
            build_description(
                heading_4_description,
                branch_context,
                effective_heading_6_description,
                subheading_context,
                description,
            )
        )

        base_rate_text = row[
            "base_rate_text"
        ]

        tariff_category = row[
            "tariff_category"
        ]

        source_excerpt = (
            f"{code} | "
            f"{full_description} | "
            f"Taux de base: "
            f"{base_rate_text} | "
            f"Catégorie: "
            f"{tariff_category}"
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

                "tariff_code":
                    code,

                "hs4_code":
                    hs4_code,

                "nomenclature_version":
                    tariff_config.get(
                        "nomenclature_version"
                    ),

                "heading_4_description":
                    heading_4_description,

                "branch_context":
                    " — ".join(
                        branch_context
                    ),

                "heading_6_code":
                    effective_heading_6_code,

                "heading_6_description":
                    effective_heading_6_description,

                "subheading_context":
                    " — ".join(
                        subheading_context
                    ),

                "leaf_description":
                    description,

                "description":
                    full_description,

                "base_rate_pct":
                    parse_rate(
                        base_rate_text
                    ),

                "base_rate_text":
                    base_rate_text,

                "tariff_category":
                    tariff_category,

                "entry_price_text":
                    row[
                        "entry_price_text"
                    ],

                "source_document":
                    config[
                        "source_document"
                    ],

                "source_section":
                    tariff_config.get(
                        "source_section"
                    ),

                "source_page":
                    row[
                        "page"
                    ],

                "source_excerpt":
                    source_excerpt,
            }
        )

        previous_code = code

    return cleaned_rows


def clean_agreement(
    agreement_key: str,
):
    config = get_agreement_config(
        agreement_key
    )

    tariff_config = config.get(
        "tariff_schedule"
    )

    if tariff_config is None:
        raise ValueError(
            f"No tariff_schedule configured "
            f"for agreement: "
            f"{agreement_key}"
        )

    page_numbers = tariff_config[
        "pages"
    ]

    raw_dir = Path(
        tariff_config[
            "raw_dir"
        ]
    )

    clean_dir = Path(
        tariff_config[
            "clean_dir"
        ]
    )

    output_path = (
        clean_dir
        / "tariff-lines.csv"
    )

    print(
        f"\nCleaning FTA tariff schedule: "
        f"{agreement_key}"
    )

    print(
        f"Pages: {page_numbers}"
    )

    # ----------------------------------------
    # Reuse complete cleaned tariff schedule
    # if it exists locally or in S3.
    #
    # We cache the complete output rather
    # than individual cleaned pages because
    # hierarchy may cross page boundaries.
    # ----------------------------------------

    if restore_cached_file(
        output_path
    ):
        print(
            f"Using cached cleaned FTA "
            f"tariff schedule: "
            f"{output_path}"
        )

        return output_path

    # ----------------------------------------
    # Each required raw page is restored
    # from S3 if necessary.
    #
    # read_tariff_pages() then creates one
    # continuous stream across all pages.
    # ----------------------------------------

    rows = read_tariff_pages(
        raw_dir=raw_dir,
        page_numbers=page_numbers,
    )

    cleaned_rows = clean_tariff_rows(
        rows=rows,
        config=config,
    )

    result = pd.DataFrame(
        cleaned_rows
    )

    clean_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    result.to_csv(
        output_path,
        index=False,
    )

    print(
        f"Cleaned {len(result)} "
        f"FTA tariff lines"
    )

    print(
        f"Saved: {output_path}"
    )

    # ----------------------------------------
    # Persist complete cleaned schedule.
    # ----------------------------------------

    persist_file(
        output_path
    )

    if not result.empty:

        print()

        print(
            result[
                [
                    "tariff_code",
                    "description",
                    "base_rate_pct",
                    "tariff_category",
                    "source_page",
                ]
            ].to_string(
                index=False
            )
        )

    return output_path


def main():

    fta_config = load_fta_config()

    supported_agreements = [
        key
        for key, config
        in fta_config.items()
        if "tariff_schedule"
        in config
    ]

    parser = argparse.ArgumentParser(
        description=(
            "Clean extracted FTA tariff "
            "schedule tables."
        )
    )

    parser.add_argument(
        "agreement",
        choices=supported_agreements,
    )

    args = parser.parse_args()

    clean_agreement(
        args.agreement
    )


if __name__ == "__main__":
    main()
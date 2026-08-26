from pathlib import Path
import argparse
import csv

import psycopg

from regulatory_engine.fta.config import (
    load_fta_config,
    get_agreement_config,
)
from regulatory_engine.settings import (
    DATABASE_URL,
)


def optional_text(value):
    if value is None:
        return None

    value = str(value).strip()

    return value or None


def optional_float(value):
    value = optional_text(value)

    if value is None:
        return None

    return float(value)


def load_tariff_lines(
    csv_path: Path,
    agreement_code: str,
):
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Cleaned tariff CSV not found: "
            f"{csv_path}"
        )

    with csv_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:
        rows = list(
            csv.DictReader(file)
        )

    if not rows:
        raise ValueError(
            f"No tariff lines found in "
            f"{csv_path}"
        )

    with psycopg.connect(
        DATABASE_URL
    ) as conn:

        with conn.cursor() as cur:

            # Rebuild this agreement's historical
            # tariff schedule deterministically.
            cur.execute(
                """
                DELETE FROM fta_tariff_lines
                WHERE agreement_code = %s
                """,
                (
                    agreement_code,
                ),
            )

            for row in rows:

                cur.execute(
                    """
                    INSERT INTO fta_tariff_lines (
                        agreement_code,
                        exporter_country,
                        importer_region,

                        tariff_code,
                        hs4_code,
                        nomenclature_version,

                        heading_4_description,
                        branch_context,

                        heading_6_code,
                        heading_6_description,

                        subheading_context,
                        leaf_description,
                        description,

                        base_rate_pct,
                        base_rate_text,
                        tariff_category,

                        source_document,
                        source_section,
                        source_page,
                        source_excerpt
                    )
                    VALUES (
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s,
                        %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s, %s
                    )
                    """,
                    (
                        row[
                            "agreement_code"
                        ],
                        row[
                            "exporter_country"
                        ],
                        row[
                            "importer_region"
                        ],

                        row[
                            "tariff_code"
                        ],
                        row[
                            "hs4_code"
                        ],
                        optional_text(
                            row[
                                "nomenclature_version"
                            ]
                        ),

                        optional_text(
                            row[
                                "heading_4_description"
                            ]
                        ),
                        optional_text(
                            row[
                                "branch_context"
                            ]
                        ),

                        optional_text(
                            row[
                                "heading_6_code"
                            ]
                        ),
                        optional_text(
                            row[
                                "heading_6_description"
                            ]
                        ),

                        optional_text(
                            row[
                                "subheading_context"
                            ]
                        ),
                        optional_text(
                            row[
                                "leaf_description"
                            ]
                        ),
                        row[
                            "description"
                        ],

                        optional_float(
                            row[
                                "base_rate_pct"
                            ]
                        ),
                        optional_text(
                            row[
                                "base_rate_text"
                            ]
                        ),
                        optional_text(
                            row[
                                "tariff_category"
                            ]
                        ),

                        row[
                            "source_document"
                        ],
                        optional_text(
                            row[
                                "source_section"
                            ]
                        ),
                        int(
                            row[
                                "source_page"
                            ]
                        ),
                        optional_text(
                            row[
                                "source_excerpt"
                            ]
                        ),
                    ),
                )

        conn.commit()

    print(
        f"FTA tariff load complete: "
        f"{len(rows)} rows loaded "
        f"from {csv_path}"
    )

    return len(rows)


def load_agreement(
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
            f"No tariff schedule configured "
            f"for agreement: "
            f"{agreement_key}"
        )

    csv_path = (
        Path(
            tariff_config[
                "clean_dir"
            ]
        )
        / "tariff-lines.csv"
    )

    print(
        f"\nLoading FTA tariff schedule: "
        f"{agreement_key}"
    )

    return load_tariff_lines(
        csv_path=csv_path,
        agreement_code=config[
            "agreement_code"
        ],
    )


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
            "Load cleaned FTA tariff "
            "schedule into PostgreSQL."
        )
    )

    parser.add_argument(
        "agreement",
        choices=supported_agreements,
    )

    args = parser.parse_args()

    load_agreement(
        args.agreement
    )


if __name__ == "__main__":
    main()
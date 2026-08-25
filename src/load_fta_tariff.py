from pathlib import Path
import argparse

import pandas as pd
import psycopg

from fta_config import (
    load_fta_config,
    get_agreement_config,
)


DB_URL = (
    "postgresql://regulatory_app:"
    "local_dev_password@localhost:5433/regulatory"
)


def clean_optional(value):
    if pd.isna(value):
        return None

    value = str(value).strip()

    if not value:
        return None

    return value


def clean_numeric(value):
    if pd.isna(value):
        return None

    value = str(value).strip()

    if not value:
        return None

    return float(value)


def clean_integer(value):
    if pd.isna(value):
        return None

    value = str(value).strip()

    if not value:
        return None

    return int(float(value))


def load_tariff_lines(
    db_url: str,
    csv_path: Path,
):
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Cleaned tariff file not found: "
            f"{csv_path}"
        )

    df = pd.read_csv(
        csv_path,
        dtype={
            "tariff_code": str,
            "hs4_code": str,
            "heading_6_code": str,
        },
    )

    if df.empty:
        print(
            f"No tariff lines found in "
            f"{csv_path}"
        )
        return

    rows = []

    for row in df.itertuples(
        index=False
    ):
        rows.append(
            (
                row.agreement_code,
                row.exporter_country,
                row.importer_region,

                row.tariff_code,
                row.hs4_code,
                clean_optional(
                    row.nomenclature_version
                ),

                clean_optional(
                    row.heading_4_description
                ),

                clean_optional(
                    row.branch_context
                ),

                clean_optional(
                    row.heading_6_code
                ),

                clean_optional(
                    row.heading_6_description
                ),

                clean_optional(
                    row.subheading_context
                ),

                clean_optional(
                    row.leaf_description
                ),

                row.description,

                clean_numeric(
                    row.base_rate_pct
                ),

                clean_optional(
                    row.base_rate_text
                ),

                clean_optional(
                    row.tariff_category
                ),

                clean_optional(
                    row.entry_price_text
                ),

                row.source_document,

                clean_optional(
                    row.source_section
                ),

                clean_integer(
                    row.source_page
                ),

                row.source_excerpt,
            )
        )

    with psycopg.connect(
        db_url
    ) as conn:

        with conn.cursor() as cur:

            cur.executemany(
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
                    entry_price_text,

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
                    %s, %s,
                    %s,
                    %s, %s,
                    %s, %s,
                    %s, %s, %s, %s
                )
                ON CONFLICT (
                    agreement_code,
                    tariff_code
                )
                DO UPDATE SET
                    exporter_country =
                        EXCLUDED.exporter_country,

                    importer_region =
                        EXCLUDED.importer_region,

                    hs4_code =
                        EXCLUDED.hs4_code,

                    nomenclature_version =
                        EXCLUDED.nomenclature_version,

                    heading_4_description =
                        EXCLUDED.heading_4_description,

                    branch_context =
                        EXCLUDED.branch_context,

                    heading_6_code =
                        EXCLUDED.heading_6_code,

                    heading_6_description =
                        EXCLUDED.heading_6_description,

                    subheading_context =
                        EXCLUDED.subheading_context,

                    leaf_description =
                        EXCLUDED.leaf_description,

                    description =
                        EXCLUDED.description,

                    base_rate_pct =
                        EXCLUDED.base_rate_pct,

                    base_rate_text =
                        EXCLUDED.base_rate_text,

                    tariff_category =
                        EXCLUDED.tariff_category,

                    entry_price_text =
                        EXCLUDED.entry_price_text,

                    source_document =
                        EXCLUDED.source_document,

                    source_section =
                        EXCLUDED.source_section,

                    source_page =
                        EXCLUDED.source_page,

                    source_excerpt =
                        EXCLUDED.source_excerpt,

                    embedding = NULL
                """,
                rows,
            )

        conn.commit()

    print(
        f"Loaded {len(rows)} tariff lines "
        f"from {csv_path}"
    )


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
            f"No tariff_schedule configured "
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

    print(
        f"CSV: {csv_path}"
    )

    load_tariff_lines(
        db_url=DB_URL,
        csv_path=csv_path,
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
            "schedule lines into PostgreSQL."
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
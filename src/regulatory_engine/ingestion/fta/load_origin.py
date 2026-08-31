from pathlib import Path
import argparse

import pandas as pd
import psycopg

from regulatory_engine.settings import DATABASE_URL

from regulatory_engine.fta.config import (
    load_fta_config,
    get_agreement_config,
)
from regulatory_engine.infrastructure.storage import (
    ensure_local_file,
)


def optional_text(value):
    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    return value


def optional_float(value):
    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    return float(value)


def load_origin_rules(
    csv_path: Path,
    db_url: str,
):
    # ----------------------------------------
    # Restore cleaned origin CSV from S3
    # if it is missing locally.
    # ----------------------------------------

    csv_path = ensure_local_file(
        Path(csv_path)
    )

    print(
        f"Loading: {csv_path}"
    )

    df = pd.read_csv(
        csv_path,
        dtype=str,
        keep_default_na=False,
    )

    processed = 0

    with psycopg.connect(
        db_url
    ) as conn:

        with conn.cursor() as cur:

            for row in df.itertuples(
                index=False
            ):

                cur.execute(
                    """
                    INSERT INTO fta_origin_rules (
                        agreement_code,
                        exporter_country,
                        importer_region,
                        hs_code,
                        description,
                        rule_text,
                        max_non_originating_material_pct,
                        value_basis,
                        source_document,
                        source_section,
                        source_page,
                        source_excerpt
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    )

                    ON CONFLICT (
                        agreement_code,
                        hs_code
                    )
                    DO UPDATE SET

                        exporter_country =
                            EXCLUDED.exporter_country,

                        importer_region =
                            EXCLUDED.importer_region,

                        description =
                            EXCLUDED.description,

                        rule_text =
                            EXCLUDED.rule_text,

                        max_non_originating_material_pct =
                            EXCLUDED.max_non_originating_material_pct,

                        value_basis =
                            EXCLUDED.value_basis,

                        source_document =
                            EXCLUDED.source_document,

                        source_section =
                            EXCLUDED.source_section,

                        source_page =
                            EXCLUDED.source_page,

                        source_excerpt =
                            EXCLUDED.source_excerpt
                    """,
                    (
                        row.agreement_code,

                        row.exporter_country,

                        row.importer_region,

                        row.hs_code,

                        optional_text(
                            row.description
                        ),

                        row.rule_text,

                        optional_float(
                            row.max_non_originating_material_pct
                        ),

                        optional_text(
                            row.value_basis
                        ),

                        row.source_document,

                        row.source_section,

                        int(
                            row.source_page
                        ),

                        row.source_excerpt,
                    ),
                )

                processed += 1

        conn.commit()

    print(
        f"FTA origin load complete: "
        f"{processed} rows upserted "
        f"from {csv_path}"
    )

    return processed


def load_agreement(
    agreement_key: str,
):
    """
    Load every configured cleaned origin page
    for one agreement.
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

    clean_dir = Path(
        origin_config[
            "clean_dir"
        ]
    )

    print(
        f"\nLoading FTA origin rules: "
        f"{agreement_key}"
    )

    print(
        f"Pages: {page_numbers}"
    )

    total = 0

    for page_number in page_numbers:

        csv_path = (
            clean_dir
            / f"page-{page_number}.csv"
        )

        total += load_origin_rules(
            csv_path=csv_path,
            db_url=DATABASE_URL,
        )

    print(
        f"Total origin rows loaded "
        f"for {agreement_key}: {total}"
    )

    return total


def main():

    fta_config = load_fta_config()

    parser = argparse.ArgumentParser(
        description=(
            "Load cleaned FTA origin rules "
            "into PostgreSQL."
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

        total = 0

        for agreement_key in (
            fta_config.keys()
        ):
            total += load_agreement(
                agreement_key
            )

        print(
            f"\nTotal FTA origin rows "
            f"upserted: {total}"
        )

    else:

        load_agreement(
            args.agreement
        )


if __name__ == "__main__":
    main()
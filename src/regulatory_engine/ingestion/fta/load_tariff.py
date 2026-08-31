from pathlib import Path
import argparse
import csv

import psycopg

from regulatory_engine.fta.config import (
    load_fta_config,
    get_agreement_config,
)
from regulatory_engine.infrastructure.storage import (
    ensure_local_file,
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
    value = optional_text(
        value
    )

    if value is None:
        return None

    return float(
        value
    )


def load_tariff_lines(
    csv_path: Path,
    agreement_code: str,
):
    # ----------------------------------------
    # Restore cleaned tariff CSV from S3
    # if it is missing locally.
    # ----------------------------------------

    csv_path = ensure_local_file(
        Path(csv_path)
    )

    print(
        f"Loading: {csv_path}"
    )

    with csv_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:

        rows = list(
            csv.DictReader(
                file
            )
        )

    if not rows:
        raise ValueError(
            f"No tariff lines found in "
            f"{csv_path}"
        )

    source_tariff_codes = [
        row[
            "tariff_code"
        ]
        for row in rows
    ]

    processed = 0

    with psycopg.connect(
        DATABASE_URL
    ) as conn:

        with conn.cursor() as cur:

            # --------------------------------
            # Upsert every tariff line.
            #
            # Existing embeddings are kept
            # unless searchable description
            # content changes.
            # --------------------------------

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

                        source_document =
                            EXCLUDED.source_document,

                        source_section =
                            EXCLUDED.source_section,

                        source_page =
                            EXCLUDED.source_page,

                        source_excerpt =
                            EXCLUDED.source_excerpt,

                        embedding =
                            CASE
                                WHEN
                                    fta_tariff_lines.description
                                    IS DISTINCT FROM
                                    EXCLUDED.description
                                THEN NULL
                                ELSE
                                    fta_tariff_lines.embedding
                            END
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

                processed += 1

            # --------------------------------
            # Remove tariff codes that were
            # previously loaded for this
            # agreement but no longer exist
            # in the cleaned source.
            #
            # This preserves deterministic
            # rebuild behaviour without
            # deleting unchanged embeddings.
            # --------------------------------

            cur.execute(
                """
                DELETE FROM fta_tariff_lines
                WHERE agreement_code = %s
                  AND NOT (
                      tariff_code = ANY(%s)
                  )
                """,
                (
                    agreement_code,
                    source_tariff_codes,
                ),
            )

        conn.commit()

    print(
        f"FTA tariff load complete: "
        f"{processed} rows upserted "
        f"from {csv_path}"
    )

    return processed


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
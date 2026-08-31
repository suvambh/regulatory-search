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


def load_legal_chunks(
    csv_path: Path,
    db_url: str,
):
    # ----------------------------------------
    # Restore cleaned legal CSV from S3
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
                    INSERT INTO fta_chunks (
                        agreement_code,
                        agreement_name,
                        exporter_country,
                        importer_region,
                        chunk_type,
                        article,
                        section,
                        text,
                        source_document,
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
                        %s
                    )

                    ON CONFLICT (
                        agreement_code,
                        chunk_type,
                        article,
                        source_page
                    )
                    DO UPDATE SET

                        agreement_name =
                            EXCLUDED.agreement_name,

                        exporter_country =
                            EXCLUDED.exporter_country,

                        importer_region =
                            EXCLUDED.importer_region,

                        section =
                            EXCLUDED.section,

                        text =
                            EXCLUDED.text,

                        source_document =
                            EXCLUDED.source_document,

                        source_excerpt =
                            EXCLUDED.source_excerpt,

                        embedding =
                            CASE
                                WHEN fta_chunks.text
                                     IS DISTINCT FROM
                                     EXCLUDED.text
                                THEN NULL
                                ELSE fta_chunks.embedding
                            END
                    """,
                    (
                        row.agreement_code,

                        row.agreement_name,

                        row.exporter_country,

                        row.importer_region,

                        row.chunk_type,

                        optional_text(
                            row.article
                        ),

                        optional_text(
                            row.section
                        ),

                        row.text,

                        row.source_document,

                        int(
                            row.source_page
                        ),

                        optional_text(
                            row.source_excerpt
                        ),
                    ),
                )

                processed += 1

        conn.commit()

    print(
        f"FTA legal load complete: "
        f"{processed} chunks upserted "
        f"from {csv_path}"
    )

    return processed


def load_agreement(
    agreement_key: str,
):

    config = get_agreement_config(
        agreement_key
    )

    csv_path = Path(
        config[
            "legal"
        ][
            "clean_path"
        ]
    )

    print(
        f"\nLoading FTA legal chunks: "
        f"{agreement_key}"
    )

    return load_legal_chunks(
        csv_path=csv_path,
        db_url=DATABASE_URL,
    )


def main():

    fta_config = load_fta_config()

    parser = argparse.ArgumentParser(
        description=(
            "Load cleaned FTA legal chunks "
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
            f"\nTotal legal chunks "
            f"upserted: {total}"
        )

    else:

        load_agreement(
            args.agreement
        )


if __name__ == "__main__":
    main()
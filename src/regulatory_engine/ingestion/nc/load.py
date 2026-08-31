from pathlib import Path

import pandas as pd

from regulatory_engine.infrastructure.database import (
    connect_db,
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


def optional_int(value):
    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    return int(value)


def optional_bool(value):
    """
    Boolean field where an empty value means NULL.

    Used for hierarchy levels that may not exist.
    """

    if value is None:
        return None

    value = str(value).strip().lower()

    if not value:
        return None

    if value in {
        "true",
        "1",
        "yes",
        "y",
    }:
        return True

    if value in {
        "false",
        "0",
        "no",
        "n",
    }:
        return False

    raise ValueError(
        f"Invalid boolean value: {value}"
    )


def parse_bool(value):
    """
    Boolean field that must always resolve
    to True or False.
    """

    if value is None:
        return False

    value = str(value).strip().lower()

    if not value:
        return False

    if value in {
        "true",
        "1",
        "yes",
        "y",
    }:
        return True

    if value in {
        "false",
        "0",
        "no",
        "n",
    }:
        return False

    raise ValueError(
        f"Invalid boolean value: {value}"
    )


def load_csv_files(
    csv_paths,
    db_url: str | None = None,
):
    processed = 0

    with connect_db(
        db_url
    ) as conn:

        with conn.cursor() as cur:

            for csv_path in csv_paths:

                # ----------------------------------------
                # Ensure cleaned CSV is available locally.
                #
                # Local mode:
                #   reuse existing file.
                #
                # S3 mode:
                #   restore processed/cleaned/... from S3
                #   when the local file is absent.
                # ----------------------------------------

                csv_path = ensure_local_file(
                    Path(csv_path)
                )

                print(
                    f"Loading: {csv_path}"
                )

                # Keep codes and text exactly as stored
                # in the cleaned CSV.
                df = pd.read_csv(
                    csv_path,
                    dtype=str,
                    keep_default_na=False,
                )

                for row in df.itertuples(
                    index=False
                ):

                    cur.execute(
                        """
                        INSERT INTO tariff_items (
                            nc_code,
                            description,

                            heading_4_code,
                            heading_4_description,

                            intermediate_heading,
                            intermediate_is_residual,

                            heading_6_code,
                            heading_6_description,
                            heading_6_is_residual,

                            subheading,
                            subheading_is_residual,

                            leaf_description,
                            leaf_is_residual,

                            parent_code,
                            has_residual_ancestor,

                            duty_rate,
                            duty_text,
                            supplementary_unit,

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

                        ON CONFLICT (nc_code)
                        DO UPDATE SET

                            description =
                                EXCLUDED.description,

                            heading_4_code =
                                EXCLUDED.heading_4_code,

                            heading_4_description =
                                EXCLUDED.heading_4_description,

                            intermediate_heading =
                                EXCLUDED.intermediate_heading,

                            intermediate_is_residual =
                                EXCLUDED.intermediate_is_residual,

                            heading_6_code =
                                EXCLUDED.heading_6_code,

                            heading_6_description =
                                EXCLUDED.heading_6_description,

                            heading_6_is_residual =
                                EXCLUDED.heading_6_is_residual,

                            subheading =
                                EXCLUDED.subheading,

                            subheading_is_residual =
                                EXCLUDED.subheading_is_residual,

                            leaf_description =
                                EXCLUDED.leaf_description,

                            leaf_is_residual =
                                EXCLUDED.leaf_is_residual,

                            parent_code =
                                EXCLUDED.parent_code,

                            has_residual_ancestor =
                                EXCLUDED.has_residual_ancestor,

                            duty_rate =
                                EXCLUDED.duty_rate,

                            duty_text =
                                EXCLUDED.duty_text,

                            supplementary_unit =
                                EXCLUDED.supplementary_unit,

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
                                        tariff_items.description
                                        IS DISTINCT FROM
                                        EXCLUDED.description
                                    THEN NULL
                                    ELSE
                                        tariff_items.embedding
                                END
                        """,
                        (
                            str(
                                row.nc_code
                            ),
                            row.description,

                            optional_text(
                                row.heading_4_code
                            ),
                            optional_text(
                                row.heading_4_description
                            ),

                            optional_text(
                                row.intermediate_heading
                            ),
                            optional_bool(
                                row.intermediate_is_residual
                            ),

                            optional_text(
                                row.heading_6_code
                            ),
                            optional_text(
                                row.heading_6_description
                            ),
                            optional_bool(
                                row.heading_6_is_residual
                            ),

                            optional_text(
                                row.subheading
                            ),
                            optional_bool(
                                row.subheading_is_residual
                            ),

                            optional_text(
                                row.leaf_description
                            ),
                            parse_bool(
                                row.leaf_is_residual
                            ),

                            optional_text(
                                row.parent_code
                            ),
                            parse_bool(
                                row.has_residual_ancestor
                            ),

                            optional_float(
                                row.duty_rate
                            ),
                            optional_text(
                                row.duty_text
                            ),
                            optional_text(
                                row.supplementary_unit
                            ),

                            optional_text(
                                row.source_document
                            ),
                            optional_text(
                                row.source_section
                            ),
                            optional_int(
                                row.source_page
                            ),
                            optional_text(
                                row.source_excerpt
                            ),
                        ),
                    )

                    processed += 1

                print(
                    f"Processed: {csv_path}"
                )

        conn.commit()

    print(
        f"Load complete: "
        f"{processed} rows upserted"
    )
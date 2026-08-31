from regulatory_engine.infrastructure.database import (
    connect_db,
)


def get_tariff_item(
    nc_code: str,
    db_url: str | None = None,
):
    """
    Retrieve the authoritative tariff row by exact NC code.

    Vector search is deliberately not used here.
    """

    with connect_db(
        db_url
    ) as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    nc_code,
                    description,
                    duty_rate,
                    duty_text,
                    supplementary_unit,
                    source_document,
                    source_section,
                    source_page,
                    source_excerpt
                FROM tariff_items
                WHERE nc_code = %s
                """,
                (
                    nc_code,
                ),
            )

            row = cur.fetchone()

    if row is None:
        return None

    return {
        "nc_code":
            row[0],

        "description":
            row[1],

        "duty_rate": (
            float(row[2])
            if row[2] is not None
            else None
        ),

        "duty_text":
            row[3],

        "supplementary_unit":
            row[4],

        "source_document":
            row[5],

        "source_section":
            row[6],

        "source_page":
            row[7],

        "source_excerpt":
            row[8],
    }
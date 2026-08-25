from regulatory_engine.infrastructure.database import (
    connect_db,
)


def find_legal_basis(
    agreement_code: str,
):
    with connect_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    article,
                    section,
                    text,
                    source_document,
                    source_page,
                    source_excerpt
                FROM fta_chunks
                WHERE agreement_code = %s
                  AND chunk_type = 'agreement_article'
                ORDER BY
                    source_page,
                    article;
                """,
                (
                    agreement_code,
                ),
            )

            rows = cur.fetchall()

    return [
        {
            "article": row[0],
            "section": row[1],
            "text": row[2],
            "source_document": row[3],
            "source_page": row[4],
            "source_excerpt": row[5],
        }
        for row in rows
    ]


def find_origin_rule(
    agreement_code: str,
    nc_code: str,
):
    if not nc_code:
        return None

    nc_code = str(
        nc_code
    ).strip()

    if len(nc_code) < 4:
        return None

    hs_code = nc_code[:4]

    with connect_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    hs_code,
                    description,
                    rule_text,
                    max_non_originating_material_pct,
                    value_basis,
                    source_document,
                    source_section,
                    source_page,
                    source_excerpt
                FROM fta_origin_rules
                WHERE agreement_code = %s
                  AND hs_code = %s
                LIMIT 1;
                """,
                (
                    agreement_code,
                    hs_code,
                ),
            )

            row = cur.fetchone()

    if row is None:
        return None

    return {
        "hs_code": row[0],
        "description": row[1],
        "rule_text": row[2],

        "max_non_originating_material_pct": (
            float(row[3])
            if row[3] is not None
            else None
        ),

        "value_basis": row[4],
        "source_document": row[5],
        "source_section": row[6],
        "source_page": row[7],
        "source_excerpt": row[8],
    }
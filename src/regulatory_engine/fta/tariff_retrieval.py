from regulatory_engine.infrastructure.database import (
    connect_db,
)
from regulatory_engine.infrastructure.embeddings import (
    embed_query,
    vector_to_pg,
)


def search_fta_tariff_lines(
    agreement_code: str,
    nc_code: str,
    product_description: str,
    limit: int = 5,
):
    hs4_code = nc_code[:4]

    query_embedding = (
        embed_query(
            product_description
        )
    )

    vector = vector_to_pg(
        query_embedding
    )

    with connect_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    tariff_code,
                    description,
                    base_rate_pct,
                    base_rate_text,
                    tariff_category,
                    source_page,
                    source_excerpt,
                    1 - (
                        embedding
                        <=> %s::vector
                    ) AS similarity
                FROM fta_tariff_lines
                WHERE
                    agreement_code = %s
                    AND hs4_code = %s
                    AND embedding IS NOT NULL
                ORDER BY
                    embedding
                    <=> %s::vector
                LIMIT %s
                """,
                (
                    vector,
                    agreement_code,
                    hs4_code,
                    vector,
                    limit,
                ),
            )

            return cur.fetchall()
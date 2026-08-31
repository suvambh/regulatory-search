from regulatory_engine.infrastructure.database import (
    connect_db,
)
from regulatory_engine.infrastructure.embeddings import (
    embed_query,
    vector_to_pg,
)


def retrieve_candidates(
    product,
    limit=5,
):
    query_embedding = (
        embed_query(
            product
        )
    )

    vector = vector_to_pg(
        query_embedding
    )

    with connect_db() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                WITH query AS (
                    SELECT %s::vector AS embedding
                )
                SELECT
                    tariff_items.nc_code,
                    tariff_items.description,
                    tariff_items.duty_rate,

                    1 - (
                        tariff_items.embedding
                        <=> query.embedding
                    ) AS similarity,

                    tariff_items.heading_4_code,
                    tariff_items.heading_4_description,

                    tariff_items.intermediate_heading,
                    tariff_items.intermediate_is_residual,

                    tariff_items.heading_6_code,
                    tariff_items.heading_6_description,
                    tariff_items.heading_6_is_residual,

                    tariff_items.subheading,
                    tariff_items.subheading_is_residual,

                    tariff_items.leaf_description,
                    tariff_items.leaf_is_residual,

                    tariff_items.parent_code,
                    tariff_items.has_residual_ancestor

                FROM tariff_items
                CROSS JOIN query

                WHERE
                    tariff_items.embedding
                    IS NOT NULL

                ORDER BY
                    tariff_items.embedding
                    <=> query.embedding

                LIMIT %s;
                """,
                (
                    vector,
                    limit,
                ),
            )

            return cur.fetchall()
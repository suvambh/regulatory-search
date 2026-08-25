import json

from regulatory_engine.infrastructure.bedrock import (
    get_bedrock_client,
)
from regulatory_engine.infrastructure.database import (
    connect_db,
)
from regulatory_engine.settings import EMBEDDING_MODEL


def vector_to_string(vector):
    return "[" + ",".join(
        str(x) for x in vector
    ) + "]"


def retrieve_candidates(
    product,
    limit=5,
):
    bedrock = get_bedrock_client()

    response = bedrock.invoke_model(
        modelId=EMBEDDING_MODEL,
        body=json.dumps(
            {
                "texts": [product],
                "input_type": "search_query",
            }
        ),
    )

    result = json.loads(
        response["body"].read()
    )

    query_embedding = (
        result["embeddings"][0]
    )

    vector = vector_to_string(
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
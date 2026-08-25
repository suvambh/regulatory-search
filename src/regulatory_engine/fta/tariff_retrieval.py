import json

from regulatory_engine.infrastructure.bedrock import (
    get_bedrock_client,
)
from regulatory_engine.infrastructure.database import (
    connect_db,
)
from regulatory_engine.settings import (
    EMBEDDING_MODEL,
)


def vector_to_string(vector):
    return "[" + ",".join(
        str(x)
        for x in vector
    ) + "]"


def embed_query(
    text: str,
):
    bedrock = get_bedrock_client()

    response = bedrock.invoke_model(
        modelId=EMBEDDING_MODEL,
        body=json.dumps(
            {
                "texts": [
                    text
                ],
                "input_type":
                    "search_query",
            }
        ),
    )

    body = json.loads(
        response[
            "body"
        ].read()
    )

    return body[
        "embeddings"
    ][0]


def search_fta_tariff_lines(
    agreement_code: str,
    nc_code: str,
    product_description: str,
    limit: int = 5,
):
    hs4_code = nc_code[:4]

    query_embedding = embed_query(
        product_description
    )

    vector = vector_to_string(
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
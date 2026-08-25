import json

import boto3
import psycopg


DB_URL = (
    "postgresql://regulatory_app:"
    "local_dev_password@localhost:5433/regulatory"
)

MODEL_ID = "cohere.embed-multilingual-v3"

bedrock = boto3.client(
    "bedrock-runtime",
    region_name="eu-west-3",
)


def vector_to_string(vector):
    return "[" + ",".join(
        str(x)
        for x in vector
    ) + "]"


def embed_query(text: str):

    response = bedrock.invoke_model(
        modelId=MODEL_ID,
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

    with psycopg.connect(
        DB_URL
    ) as conn:

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

            rows = cur.fetchall()

    return rows


def main():

    rows = search_fta_tariff_lines(
        agreement_code="EU_KOREA_FTA",
        nc_code="85285291",
        product_description=(
            "Moniteur LCD couleur conçu "
            "pour être connecté directement "
            "à une machine automatique de "
            "traitement de l'information"
        ),
    )

    print(
        "\n--- FTA TARIFF SEARCH ---\n"
    )

    for row in rows:

        (
            tariff_code,
            description,
            base_rate_pct,
            base_rate_text,
            tariff_category,
            source_page,
            source_excerpt,
            similarity,
        ) = row

        print(
            f"Code: {tariff_code}"
        )

        print(
            f"Similarity: "
            f"{similarity:.4f}"
        )

        print(
            f"Base rate: "
            f"{base_rate_pct}"
        )

        print(
            f"Category: "
            f"{tariff_category}"
        )

        print(
            f"Description: "
            f"{description}"
        )

        print(
            f"Source page: "
            f"{source_page}"
        )

        print(
            "-" * 80
        )


if __name__ == "__main__":
    main()
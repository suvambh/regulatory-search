import json

import boto3
import psycopg

from regulatory_engine.settings import (
    AWS_REGION,
    EMBEDDING_MODEL,
)


bedrock = boto3.client(
    "bedrock-runtime",
    region_name=AWS_REGION,
)


def vector_to_string(vector):
    return "[" + ",".join(
        str(x)
        for x in vector
    ) + "]"


def embed_tariff_items(
    db_url: str,
):
    with psycopg.connect(
        db_url
    ) as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    id,
                    nc_code,
                    description
                FROM tariff_items
                WHERE embedding IS NULL
                ORDER BY id
                """
            )

            rows = cur.fetchall()

            if not rows:
                print(
                    "Nothing to embed"
                )
                return

            total = len(
                rows
            )

            print(
                f"{total} tariff items "
                f"need embeddings"
            )

            print(
                f"Embedding model: "
                f"{EMBEDDING_MODEL}"
            )

            for index, row in enumerate(
                rows,
                start=1,
            ):

                row_id = row[0]
                nc_code = row[1]
                description = row[2]

                text = (
                    f"Code NC: "
                    f"{nc_code}\n"
                    f"Description: "
                    f"{description}"
                )

                response = (
                    bedrock.invoke_model(
                        modelId=(
                            EMBEDDING_MODEL
                        ),
                        body=json.dumps(
                            {
                                "texts": [
                                    text
                                ],
                                "input_type": (
                                    "search_document"
                                ),
                                "truncate": (
                                    "END"
                                ),
                            }
                        ),
                        contentType=(
                            "application/json"
                        ),
                        accept=(
                            "application/json"
                        ),
                    )
                )

                result = json.loads(
                    response[
                        "body"
                    ].read()
                )

                embedding = (
                    result[
                        "embeddings"
                    ][0]
                )

                cur.execute(
                    """
                    UPDATE tariff_items
                    SET embedding = %s::vector
                    WHERE id = %s
                    """,
                    (
                        vector_to_string(
                            embedding
                        ),
                        row_id,
                    ),
                )

                print(
                    f"Embedded "
                    f"{index}/{total}: "
                    f"{nc_code}"
                )

        conn.commit()

    print(
        f"Embedded "
        f"{total} tariff items"
    )
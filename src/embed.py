import json

import boto3
import psycopg


MODEL_ID = "cohere.embed-multilingual-v3"

bedrock = boto3.client(
    "bedrock-runtime",
    region_name="eu-west-3",
)


def vector_to_string(vector):
    return "[" + ",".join(
        str(x) for x in vector
    ) + "]"


def embed_tariff_items(
    db_url: str,
):
    with psycopg.connect(db_url) as conn:
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
                print("Nothing to embed")
                return

            total = len(rows)

            print(
                f"{total} tariff items "
                f"need embeddings"
            )

            for index, row in enumerate(
                rows,
                start=1,
            ):
                row_id = row[0]
                nc_code = row[1]
                description = row[2]

                text = (
                    f"Code NC: {nc_code}\n"
                    f"Description: {description}"
                )

                response = bedrock.invoke_model(
                    modelId=MODEL_ID,
                    body=json.dumps(
                        {
                            "texts": [text],
                            "input_type": (
                                "search_document"
                            ),
                            "truncate": "END",
                        }
                    ),
                    contentType="application/json",
                    accept="application/json",
                )

                result = json.loads(
                    response["body"].read()
                )

                embedding = (
                    result["embeddings"][0]
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
        f"Embedded {total} tariff items"
    )
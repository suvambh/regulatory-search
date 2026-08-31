from regulatory_engine.infrastructure.embeddings import (
    embed_document,
    vector_to_pg,
)
from regulatory_engine.settings import (
    EMBEDDING_MODEL,
)

from regulatory_engine.infrastructure.database import (
    connect_db,
)

def embed_tariff_items(
    db_url: str | None = None,
):
    with connect_db(
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

                embedding = (
                    embed_document(
                        text
                    )
                )

                cur.execute(
                    """
                    UPDATE tariff_items
                    SET embedding = %s::vector
                    WHERE id = %s
                    """,
                    (
                        vector_to_pg(
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
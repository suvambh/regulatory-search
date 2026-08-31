from regulatory_engine.infrastructure.database import (
    connect_db,
)
from regulatory_engine.infrastructure.embeddings import (
    embed_document,
    vector_to_pg,
)
from regulatory_engine.settings import (
    DATABASE_URL,
)


def build_embedding_text(
    branch_context,
    heading_6_description,
    subheading_context,
    leaf_description,
):
    """
    Build a compact, discriminative description
    for semantic search.

    We intentionally exclude the very broad HS4
    description because it is shared by many
    sibling tariff lines and reduces retrieval
    precision.
    """

    parts = [
        branch_context,
        heading_6_description,
        subheading_context,
        leaf_description,
    ]

    cleaned_parts = []

    for part in parts:

        if part is None:
            continue

        part = str(
            part
        ).strip()

        if not part:
            continue

        if part in cleaned_parts:
            continue

        cleaned_parts.append(
            part
        )

    return " — ".join(
        cleaned_parts
    )


def embed_tariff_lines(
    db_url: str = DATABASE_URL,
):

    with connect_db(
        db_url
    ) as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    id,
                    tariff_code,
                    branch_context,
                    heading_6_description,
                    subheading_context,
                    leaf_description
                FROM fta_tariff_lines
                WHERE embedding IS NULL
                ORDER BY id
                """
            )

            rows = cur.fetchall()

            if not rows:
                print(
                    "Nothing to embed"
                )
                return 0

            embedded = 0

            for (
                row_id,
                tariff_code,
                branch_context,
                heading_6_description,
                subheading_context,
                leaf_description,
            ) in rows:

                text = build_embedding_text(
                    branch_context=(
                        branch_context
                    ),
                    heading_6_description=(
                        heading_6_description
                    ),
                    subheading_context=(
                        subheading_context
                    ),
                    leaf_description=(
                        leaf_description
                    ),
                )

                if not text:
                    print(
                        f"Skipping "
                        f"{tariff_code}: "
                        f"no embedding text"
                    )
                    continue

                embedding = (
                    embed_document(
                        text
                    )
                )

                cur.execute(
                    """
                    UPDATE fta_tariff_lines
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

                embedded += 1

                print(
                    f"Embedded "
                    f"{tariff_code}"
                )

                print(
                    f"  {text}"
                )

        conn.commit()

    print(
        f"\nFTA tariff embeddings "
        f"complete: {embedded} embedded."
    )

    return embedded


def main():

    embed_tariff_lines(
        db_url=DATABASE_URL
    )


if __name__ == "__main__":
    main()
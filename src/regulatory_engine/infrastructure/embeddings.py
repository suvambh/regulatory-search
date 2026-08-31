import json

from regulatory_engine.infrastructure.bedrock import (
    get_bedrock_client,
)
from regulatory_engine.settings import (
    EMBEDDING_MODEL,
)


def embed_text(
    text: str,
    *,
    input_type: str,
    truncate: str | None = None,
) -> list[float]:
    """
    Generate one Bedrock embedding.

    Supported Cohere input types used by the application:

    - search_query:
        runtime buyer/product queries

    - search_document:
        regulatory records embedded during ingestion
    """

    if not text:
        raise ValueError(
            "Cannot embed empty text."
        )

    payload = {
        "texts": [
            text
        ],
        "input_type":
            input_type,
    }

    if truncate is not None:
        payload[
            "truncate"
        ] = truncate

    bedrock = get_bedrock_client()

    response = bedrock.invoke_model(
        modelId=EMBEDDING_MODEL,
        body=json.dumps(
            payload
        ),
        contentType=(
            "application/json"
        ),
        accept=(
            "application/json"
        ),
    )

    body = json.loads(
        response[
            "body"
        ].read()
    )

    embeddings = body.get(
        "embeddings"
    )

    if not embeddings:
        raise ValueError(
            "Embedding model returned "
            "no embeddings."
        )

    return embeddings[0]


def embed_query(
    text: str,
) -> list[float]:
    """
    Embed runtime search text.
    """

    return embed_text(
        text,
        input_type=(
            "search_query"
        ),
    )


def embed_document(
    text: str,
) -> list[float]:
    """
    Embed regulatory content during ingestion.
    """

    return embed_text(
        text,
        input_type=(
            "search_document"
        ),
        truncate="END",
    )


def vector_to_pg(
    vector: list[float],
) -> str:
    """
    Convert a numeric vector into PostgreSQL
    pgvector text representation.

    Example:

        [0.1, 0.2, 0.3]

    becomes:

        "[0.1,0.2,0.3]"
    """

    return (
        "["
        + ",".join(
            str(value)
            for value in vector
        )
        + "]"
    )
import json

import boto3
import psycopg


DB_URL = (
    "postgresql://regulatory_app:"
    "local_dev_password@localhost:5433/regulatory"
)

EMBEDDING_MODEL = "cohere.embed-multilingual-v3"
LLM_MODEL = "eu.amazon.nova-pro-v1:0"

bedrock = boto3.client(
    "bedrock-runtime",
    region_name="eu-west-3",
)


def vector_to_string(vector):
    return "[" + ",".join(str(x) for x in vector) + "]"


def format_text(value):
    """
    Format optional hierarchy text for the classifier.
    """

    if value is None:
        return "[not present]"

    value = str(value).strip()

    if not value:
        return "[not present]"

    return value


def format_residual_flag(value):
    """
    Preserve the difference between:
    - True  -> residual level
    - False -> specific level
    - None  -> hierarchy level not present
    """

    if value is None:
        return "not present"

    if value is True:
        return "yes"

    return "no"


def retrieve_candidates(product, limit=5):

    # --------------------------------------------------
    # 1. Embed the user query
    # --------------------------------------------------

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

    # --------------------------------------------------
    # 2. Retrieve semantic candidates from pgvector
    #
    # Important:
    # The first four fields remain unchanged so existing
    # code using row[0]..row[3] continues to work.
    # --------------------------------------------------

    with psycopg.connect(DB_URL) as conn:
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


def select_candidate(
    product,
    candidates,
):

    # --------------------------------------------------
    # Build structured candidate representation
    #
    # Similarity is deliberately not sent to the LLM.
    # It is only used by retrieval.
    # --------------------------------------------------

    candidate_blocks = []

    for row in candidates:

        candidate_blocks.append(
            f"""
NC CODE:
{row[0]}

HIERARCHY:

HS4 code:
{format_text(row[4])}

HS4 heading:
{format_text(row[5])}

Intermediate heading:
{format_text(row[6])}

Intermediate heading is residual:
{format_residual_flag(row[7])}

HS6 code:
{format_text(row[8])}

HS6 heading:
{format_text(row[9])}

HS6 heading is residual:
{format_residual_flag(row[10])}

Subheading:
{format_text(row[11])}

Subheading is residual:
{format_residual_flag(row[12])}

Leaf description:
{format_text(row[13])}

Leaf is residual:
{format_residual_flag(row[14])}

Parent code:
{format_text(row[15])}

Has residual ancestor:
{"yes" if row[16] else "no"}

FULL RECONSTRUCTED DESCRIPTION:
{row[1]}

DUTY RATE:
{row[2]}
""".strip()
        )

    candidate_text = (
        "\n\n"
        "========================================\n\n"
    ).join(candidate_blocks)

    # --------------------------------------------------
    # Classification prompt
    # --------------------------------------------------

    prompt = f"""
You are classifying a product into an EU Combined Nomenclature (NC) code.

Product:
{product}

Candidates:
{candidate_text}

The hierarchy is cumulative: a final NC code inherits the applicable
restrictions from all hierarchy levels shown for that candidate.

Evaluate each candidate internally using three states:

- SUPPORTED:
  explicitly stated or clearly implied by ordinary-language meaning

- CONTRADICTED:
  incompatible with something explicitly stated

- UNKNOWN:
  required information is genuinely absent

Rules:

- Evaluate the full hierarchy, not only the leaf description.

- A candidate is not supported merely because it is not contradicted.
  Necessary distinguishing restrictions must be SUPPORTED.

- Clear ordinary-language equivalence counts as support.

- Do not invent unstated characteristics such as intended use, voltage,
  composition, dimensions, construction, or performance.

- Reject candidates whose fundamental product type is incompatible with
  the input.

- Eliminate contradicted candidates before deciding whether classification
  is uncertain.

- Treat "other", "autre", "autres", and hierarchy levels marked as residual
  as residual branches.

- A specific leaf under a residual ancestor still belongs to a residual
  branch.

- Do not choose a residual branch merely because information required for
  a more specific sibling is absent.

- If a specific sibling is supported, prefer it over a residual sibling.

- If at least two genuinely plausible candidates remain and an UNKNOWN
  characteristic is required to distinguish them, return
  UNCERTAIN_CLASSIFICATION.

- Do not return UNCERTAIN_CLASSIFICATION for candidates that are contradicted
  by information already present in the product description.

- If none of the candidates describes the same fundamental product type,
  return NO_RELEVANT_CANDIDATE.

- Do not use semantic similarity as classification evidence.

- missing_information must contain only genuinely absent information needed
  to distinguish remaining plausible candidates.

Return only valid JSON. Do not include Markdown or internal analysis.

SUPPORTED:
{{
  "status": "SUPPORTED",
  "nc_code": "<code>",
  "reason": "<short reason>",
  "missing_information": []
}}

UNCERTAIN_CLASSIFICATION:
{{
  "status": "UNCERTAIN_CLASSIFICATION",
  "nc_code": null,
  "reason": "<short unresolved distinction>",
  "missing_information": [
    "<missing characteristic>"
  ]
}}

NO_RELEVANT_CANDIDATE:
{{
  "status": "NO_RELEVANT_CANDIDATE",
  "nc_code": null,
  "reason": "<short reason>",
  "missing_information": []
}}
"""

    # --------------------------------------------------
    # Call Nova
    # --------------------------------------------------

    response = bedrock.converse(
        modelId=LLM_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "text": prompt,
                    }
                ],
            }
        ],
        inferenceConfig={
            "temperature": 0,
            "maxTokens": 300,
        },
    )

    text = (
        response[
            "output"
        ][
            "message"
        ][
            "content"
        ][0][
            "text"
        ]
    )

    text = text.strip()

    if text.startswith("```json"):
        text = text[7:]

    if text.endswith("```"):
        text = text[:-3]

    return json.loads(
        text.strip()
    )


def search_and_classify(
    product,
    limit=5,
):

    candidates = retrieve_candidates(
        product,
        limit=limit,
    )

    classification = select_candidate(
        product,
        candidates,
    )

    return {
        "candidates": candidates,
        "classification": classification,
    }


if __name__ == "__main__":

    product = (
        "Écran LCD moniteur 27 pouces"
    )

    result = search_and_classify(
        product,
        limit=5,
    )

    print(
        "\n--- VECTOR SEARCH ---\n"
    )

    for row in result["candidates"]:

        print(
            f"NC code: {row[0]}"
        )

        print(
            f"Description: {row[1]}"
        )

        print(
            f"Duty rate: {row[2]}"
        )

        print(
            f"Similarity: {row[3]}"
        )

        print(
            f"HS4: {row[4]}"
        )

        print(
            f"HS6: {row[8]}"
        )

        print(
            f"Subheading: {row[11]}"
        )

        print(
            f"Leaf: {row[13]}"
        )

        print(
            "Has residual ancestor: "
            f"{row[16]}"
        )

        print()

    print(
        "\n--- NOVA CLASSIFICATION ---\n"
    )

    print(
        json.dumps(
            result["classification"],
            indent=2,
            ensure_ascii=False,
        )
    )
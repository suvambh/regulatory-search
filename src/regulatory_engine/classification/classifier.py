import json

from regulatory_engine.infrastructure.bedrock import (
    get_bedrock_client,
)
from regulatory_engine.settings import (
    CLASSIFICATION_MODEL,
)


def format_text(value):
    if value is None:
        return "[not present]"

    value = str(value).strip()

    if not value:
        return "[not present]"

    return value


def format_residual_flag(value):
    if value is None:
        return "not present"

    if value is True:
        return "yes"

    return "no"


def select_candidate(
    product,
    candidates,
):
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

    bedrock = get_bedrock_client()

    response = bedrock.converse(
        modelId=CLASSIFICATION_MODEL,
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
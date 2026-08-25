import json
import re

from regulatory_engine.fta.tariff_retrieval import (
    search_fta_tariff_lines,
)
from regulatory_engine.infrastructure.bedrock import (
    get_bedrock_client,
)
from regulatory_engine.settings import (
    CLASSIFICATION_MODEL,
)


def extract_json(text: str):
    """
    Extract a JSON object from the model response.

    Allows the model to accidentally wrap the JSON
    in markdown while still keeping parsing robust.
    """

    text = text.strip()

    if text.startswith("```"):
        text = re.sub(
            r"^```(?:json)?\s*",
            "",
            text,
        )

        text = re.sub(
            r"\s*```$",
            "",
            text,
        )

    match = re.search(
        r"\{.*\}",
        text,
        re.DOTALL,
    )

    if not match:
        raise ValueError(
            f"No JSON object found in model response:\n{text}"
        )

    return json.loads(
        match.group(0)
    )


def build_candidate_payload(
    rows,
):
    """
    Convert search results into a compact structure
    for the classifier.
    """

    candidates = []

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

        candidates.append(
            {
                "tariff_code":
                    tariff_code,

                "description":
                    description,

                "base_rate_pct":
                    (
                        float(base_rate_pct)
                        if base_rate_pct
                        is not None
                        else None
                    ),

                "base_rate_text":
                    base_rate_text,

                "tariff_category":
                    tariff_category,

                "source_page":
                    source_page,

                "source_excerpt":
                    source_excerpt,

                "similarity":
                    float(similarity),
            }
        )

    return candidates


def classify_candidates(
    product_description: str,
    nc_code: str,
    current_nc_description: str | None,
    candidates: list[dict],
):
    """
    Ask Nova to select the historical FTA tariff
    line that best corresponds to the classified
    product.

    Important:
    this only reconciles nomenclatures.
    It does NOT determine the current preferential
    customs-duty rate.
    """

    prompt = f"""
You are reconciling a current EU NC classification with an older FTA tariff nomenclature.

The current NC classification is already established.
Select the historical tariff line that best corresponds to the same product.

Rules:
- Use only the information provided.
- Do not invent tariff codes.
- Do not change the current NC classification.
- Older tariff descriptions may be broader and may omit distinctions present in the current NC.
- Do not reject a candidate only because it omits a current product attribute.
- Reject a candidate when it explicitly contradicts the product or refers to a different product type, technology, function, or use.
- Prefer the candidate that preserves the most important product characteristics and function.
- Do not calculate preferential duty rates or interpret tariff categories.

Return:
- SUPPORTED if one candidate is clearly the best match.
- UNCERTAIN if multiple candidates remain materially plausible.
- NO_RELEVANT_CANDIDATE if none is compatible.

Return JSON only:

{{
  "status": "SUPPORTED | UNCERTAIN | NO_RELEVANT_CANDIDATE",
  "tariff_code": "selected code or null",
  "reason": "short explanation"
}}

PRODUCT:
{product_description}

CURRENT NC CODE:
{nc_code}

CURRENT NC DESCRIPTION:
{current_nc_description or "Not provided"}

HISTORICAL CANDIDATES:
{json.dumps(
    candidates,
    ensure_ascii=False,
    indent=2,
)}
"""
    bedrock = get_bedrock_client()
    response = bedrock.invoke_model(
        
        modelId=CLASSIFICATION_MODEL,
        body=json.dumps(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "text": prompt
                            }
                        ],
                    }
                ],
                "inferenceConfig": {
                    "temperature": 0,
                    "maxTokens": 500,
                },
            }
        ),
    )

    body = json.loads(
        response[
            "body"
        ].read()
    )

    model_text = (
        body[
            "output"
        ][
            "message"
        ][
            "content"
        ][0][
            "text"
        ]
    )

    return extract_json(
        model_text
    )


def find_candidate(
    candidates,
    tariff_code,
):
    for candidate in candidates:

        if (
            candidate[
                "tariff_code"
            ]
            == tariff_code
        ):
            return candidate

    return None


def classify_fta_tariff_line(
    agreement_code: str,
    nc_code: str,
    product_description: str,
    current_nc_description: str | None = None,
    limit: int = 5,
):
    """
    Full historical tariff-line reconciliation:

        current NC classification
            ↓
        HS4-filtered vector retrieval
            ↓
        Nova candidate selection
            ↓
        selected historical FTA tariff line
    """

    search_rows = (
        search_fta_tariff_lines(
            agreement_code=(
                agreement_code
            ),
            nc_code=(
                nc_code
            ),
            product_description=(
                product_description
            ),
            limit=limit,
        )
    )

    if not search_rows:
        return {
            "status":
                "NO_RELEVANT_CANDIDATE",

            "tariff_code":
                None,

            "reason":
                (
                    "No historical tariff "
                    "candidates were retrieved."
                ),

            "candidate":
                None,
        }

    candidates = (
        build_candidate_payload(
            search_rows
        )
    )

    decision = classify_candidates(
        product_description=(
            product_description
        ),
        nc_code=(
            nc_code
        ),
        current_nc_description=(
            current_nc_description
        ),
        candidates=candidates,
    )

    status = decision.get(
        "status"
    )

    tariff_code = decision.get(
        "tariff_code"
    )

    reason = decision.get(
        "reason"
    )

    allowed_statuses = {
        "SUPPORTED",
        "UNCERTAIN",
        "NO_RELEVANT_CANDIDATE",
    }

    if status not in allowed_statuses:
        raise ValueError(
            f"Unexpected classifier status: "
            f"{status}"
        )

    # ----------------------------------------
    # SUPPORTED must point to an actual
    # retrieved candidate.
    # ----------------------------------------

    if status == "SUPPORTED":

        if not tariff_code:
            raise ValueError(
                "Classifier returned SUPPORTED "
                "without tariff_code."
            )

        selected_candidate = (
            find_candidate(
                candidates,
                tariff_code,
            )
        )

        if selected_candidate is None:
            raise ValueError(
                f"Classifier selected "
                f"{tariff_code}, but that code "
                f"was not in the retrieved "
                f"candidate set."
            )

        return {
            "status":
                "SUPPORTED",

            "tariff_code":
                tariff_code,

            "reason":
                reason,

            "candidate":
                selected_candidate,

            "candidates":
                candidates,
        }

    # ----------------------------------------
    # UNCERTAIN
    # ----------------------------------------

    if status == "UNCERTAIN":

        return {
            "status":
                "UNCERTAIN",

            "tariff_code":
                None,

            "reason":
                reason,

            "candidate":
                None,

            "candidates":
                candidates,
        }

    # ----------------------------------------
    # NO_RELEVANT_CANDIDATE
    # ----------------------------------------

    return {
        "status":
            "NO_RELEVANT_CANDIDATE",

        "tariff_code":
            None,

        "reason":
            reason,

        "candidate":
            None,

        "candidates":
            candidates,
    }


def main():

    result = classify_fta_tariff_line(
        agreement_code=(
            "EU_KOREA_FTA"
        ),

        nc_code=(
            "85285291"
        ),

        product_description=(
            "Moniteur LCD couleur conçu "
            "pour être connecté directement "
            "à une machine automatique de "
            "traitement de l'information"
        ),

        current_nc_description=(
            "Moniteurs capables d'être "
            "connectés directement à une "
            "machine automatique de traitement "
            "de l'information du no 8471 "
            "et conçus pour être utilisés "
            "avec celle-ci"
        ),

        limit=5,
    )

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
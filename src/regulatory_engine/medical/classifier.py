import json
import re

from regulatory_engine.infrastructure.bedrock import (
    get_bedrock_client,
)
from regulatory_engine.settings import (
    CLASSIFICATION_MODEL,
)


ALLOWED_STATUSES = {
    "SUPPORTED",
    "UNCERTAIN_CLASSIFICATION",
    "NOT_APPLICABLE",
    "UNCERTAIN_APPLICABILITY",
}


ALLOWED_CLASSES = {
    "I",
    "IIa",
    "IIb",
    "III",
}


def extract_json(
    text: str,
) -> dict:

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
            "No JSON object found in "
            "medical classifier response:\n"
            f"{text}"
        )

    return json.loads(
        match.group(0)
    )


def compact_provision(
    provision: dict,
) -> dict:
    """
    Send only the regulatory content required for
    reasoning to the model.
    """

    return {
        "provision_id":
            provision[
                "provision_id"
            ],

        "provision_code":
            provision.get(
                "provision_code"
            ),

        "title":
            provision.get(
                "title"
            ),

        "text":
            provision[
                "text"
            ],

        "source_page":
            provision[
                "source_page"
            ],
    }


def validate_decision(
    decision: dict,
    classification_rules: list[dict],
) -> dict:

    status = decision.get(
        "status"
    )

    if status not in ALLOWED_STATUSES:
        raise ValueError(
            "Unexpected medical classifier "
            f"status: {status}"
        )

    rule_ids = decision.get(
        "rule_ids",
        [],
    )

    if rule_ids is None:
        rule_ids = []

    if not isinstance(
        rule_ids,
        list,
    ):
        raise ValueError(
            "medical classifier rule_ids "
            "must be a list."
        )

    valid_rule_ids = {
        rule[
            "provision_id"
        ]
        for rule
        in classification_rules
    }

    for rule_id in rule_ids:

        if rule_id not in valid_rule_ids:
            raise ValueError(
                "Medical classifier selected "
                f"{rule_id}, but that rule was "
                "not present in the supplied "
                "regulatory evidence."
            )

    classification = decision.get(
        "classification"
    )

    if (
        classification is not None
        and classification
        not in ALLOWED_CLASSES
    ):
        raise ValueError(
            "Unexpected MDR class: "
            f"{classification}"
        )

    possible_classes = decision.get(
        "possible_classes",
        [],
    )

    if possible_classes is None:
        possible_classes = []

    for device_class in (
        possible_classes
    ):

        if (
            device_class
            not in ALLOWED_CLASSES
        ):
            raise ValueError(
                "Unexpected possible MDR "
                f"class: {device_class}"
            )

    if status == "SUPPORTED":

        if classification is None:
            raise ValueError(
                "SUPPORTED medical "
                "classification requires "
                "classification."
            )

        if not rule_ids:
            raise ValueError(
                "SUPPORTED medical "
                "classification requires "
                "at least one retrieved rule."
            )

    if (
        status
        == "UNCERTAIN_CLASSIFICATION"
        and not rule_ids
    ):
        raise ValueError(
            "UNCERTAIN_CLASSIFICATION "
            "requires at least one "
            "retrieved rule."
        )

    decision[
        "rule_ids"
    ] = rule_ids

    decision[
        "possible_classes"
    ] = possible_classes

    return decision


def classify_medical_device(
    product: str,
    *,
    applicability_evidence: list[dict],
    classification_context: list[dict],
    classification_rules: list[dict],
) -> dict:
    """
    Determine MDR applicability and, when supported,
    classify the device using only the supplied MDR
    evidence.

    The model cannot invent a classification rule:
    returned rule IDs are validated against the
    database evidence supplied to it.
    """

    applicability_payload = [
        compact_provision(
            provision
        )
        for provision
        in applicability_evidence
    ]

    context_payload = [
        compact_provision(
            provision
        )
        for provision
        in classification_context
    ]

    rules_payload = [
        compact_provision(
            provision
        )
        for provision
        in classification_rules
    ]

    prompt = f"""
You are classifying a product under Regulation (EU) 2017/745 (MDR).

PRODUCT:
{product}

MDR DEFINITIONS:
{json.dumps(
    applicability_payload,
    ensure_ascii=False,
    indent=2,
)}

ANNEX VIII CONTEXT:
{json.dumps(
    context_payload,
    ensure_ascii=False,
    indent=2,
)}

ANNEX VIII RULES:
{json.dumps(
    rules_payload,
    ensure_ascii=False,
    indent=2,
)}

Use only the product description and the regulatory evidence above.

Rules:
- Do not use outside regulatory knowledge.
- Do not invent product characteristics or intended purpose.
- First decide whether the product is a medical device under the supplied definitions.
- If MDR clearly does not apply, return NOT_APPLICABLE.
- If applicability depends on missing information, return UNCERTAIN_APPLICABILITY.
- If MDR applies, classify using only the supplied Annex VIII rules.
- A rule_id must exactly match a supplied provision_id.
- Apply the most specific matching branch of a rule.
- If the product clearly matches an explicitly named device category in a rule, apply that branch.
- Do not keep the generic class as an alternative when a more specific branch clearly applies.
- When a rule has a default class and a higher-risk exception, apply the exception only when its conditions are supported by the product description.
- If missing intended-purpose or risk information could change the class, return UNCERTAIN_CLASSIFICATION and list the possible classes.
- If several rules genuinely apply, follow the Annex VIII principle that the strictest applicable rule or sub-rule determines the class.
- missing_information must contain only facts genuinely needed to resolve the decision.

Return valid JSON only.

SUPPORTED:
{{
  "status": "SUPPORTED",
  "medical_device": true,
  "classification": "I | IIa | IIb | III",
  "possible_classes": ["selected class"],
  "rule_ids": ["supplied provision_id"],
  "reason": "short evidence-based reason",
  "missing_information": []
}}

UNCERTAIN_CLASSIFICATION:
{{
  "status": "UNCERTAIN_CLASSIFICATION",
  "medical_device": true,
  "classification": null,
  "possible_classes": ["possible class"],
  "rule_ids": ["supplied provision_id"],
  "reason": "short reason",
  "missing_information": ["missing characteristic"]
}}

NOT_APPLICABLE:
{{
  "status": "NOT_APPLICABLE",
  "medical_device": false,
  "classification": null,
  "possible_classes": [],
  "rule_ids": [],
  "reason": "short reason",
  "missing_information": []
}}

UNCERTAIN_APPLICABILITY:
{{
  "status": "UNCERTAIN_APPLICABILITY",
  "medical_device": null,
  "classification": null,
  "possible_classes": [],
  "rule_ids": [],
  "reason": "short reason",
  "missing_information": ["missing information"]
}}
"""

    bedrock = get_bedrock_client()

    response = bedrock.converse(
        modelId=CLASSIFICATION_MODEL,
        messages=[
            {
                "role":
                    "user",

                "content": [
                    {
                        "text":
                            prompt,
                    }
                ],
            }
        ],
        inferenceConfig={
            "temperature":
                0,

            "maxTokens":
                600,
        },
    )

    model_text = (
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

    decision = extract_json(
        model_text
    )

    return validate_decision(
        decision,
        classification_rules,
    )
from regulatory_engine.medical.classifier import (
    classify_medical_device,
)
from regulatory_engine.repositories.medical_repository import (
    find_medical_provisions,
    get_medical_provision,
    get_medical_provisions,
)


MDR_DOCUMENT_CODE = (
    "EU_MDR_2017_745"
)


APPLICABILITY_PROVISION_IDS = [
    "MDR_ARTICLE_2_DEFINITION_1",
    "MDR_ARTICLE_2_DEFINITION_4",
    "MDR_ARTICLE_2_DEFINITION_5",
    "MDR_ARTICLE_2_DEFINITION_12",
]


GENERAL_REGULATORY_BASIS_IDS = [
    "MDR_ARTICLE_19",
    "MDR_ARTICLE_20",
    "MDR_ARTICLE_51",
    "MDR_ARTICLE_52",
    "MDR_ARTICLE_53",
    "MDR_ANNEX_II_PAGE_108",
    "MDR_ANNEX_IV_PAGE_113",
]


def public_source(
    provision: dict,
) -> dict:
    """
    Convert a database provision into the source
    structure returned by the application.
    """

    return {
        "provision_id":
            provision[
                "provision_id"
            ],

        "provision_type":
            provision[
                "provision_type"
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

        "source_document":
            provision[
                "document_name"
            ],

        "source_section":
            provision.get(
                "source_section"
            ),

        "source_page":
            provision[
                "source_page"
            ],

        "source_excerpt":
            provision.get(
                "source_excerpt"
            ),
    }


def get_classification_context() -> list[dict]:

    context = get_medical_provision(
        "MDR_ANNEX_VIII_CONTEXT",
        document_code=(
            MDR_DOCUMENT_CODE
        ),
    )

    if context is None:
        return []

    return [
        context
    ]


def get_classification_rules() -> list[dict]:

    return find_medical_provisions(
        document_code=(
            MDR_DOCUMENT_CODE
        ),
        provision_type=(
            "classification_rule"
        ),
    )


def evaluate_medical_regulation(
    product: str,
) -> dict:
    """
    Evaluate MDR applicability and classification.

    Flow:

        product
          ↓
        structured MDR evidence
          ↓
        bounded Nova reasoning
          ↓
        validated rule IDs
          ↓
        exact regulatory source records
    """

    applicability_evidence = (
        get_medical_provisions(
            APPLICABILITY_PROVISION_IDS,
            document_code=(
                MDR_DOCUMENT_CODE
            ),
        )
    )

    classification_context = (
        get_classification_context()
    )

    classification_rules = (
        get_classification_rules()
    )

    if not applicability_evidence:
        raise ValueError(
            "MDR applicability evidence "
            "is missing from the database."
        )

    if not classification_rules:
        raise ValueError(
            "MDR classification rules "
            "are missing from the database."
        )

    decision = (
        classify_medical_device(
            product,
            applicability_evidence=(
                applicability_evidence
            ),
            classification_context=(
                classification_context
            ),
            classification_rules=(
                classification_rules
            ),
        )
    )

    status = decision[
        "status"
    ]

    # --------------------------------------------------------
    # Non-applicable / applicability unresolved
    # --------------------------------------------------------

    if status in {
        "NOT_APPLICABLE",
        "UNCERTAIN_APPLICABILITY",
    }:

        return {
            "status":
                status,

            "framework": {
                "document_code":
                    MDR_DOCUMENT_CODE,

                "document_name":
                    applicability_evidence[
                        0
                    ][
                        "document_name"
                    ],
            },

            "medical_device":
                decision.get(
                    "medical_device"
                ),

            "classification":
                None,

            "possible_classes":
                [],

            "rules":
                [],

            "reason":
                decision.get(
                    "reason"
                ),

            "missing_information":
                decision.get(
                    "missing_information",
                    [],
                ),

            "applicability_basis": [
                public_source(
                    provision
                )
                for provision
                in applicability_evidence
            ],

            "regulatory_basis":
                [],
        }

    # --------------------------------------------------------
    # Medical device classification
    # --------------------------------------------------------

    rules_by_id = {
        rule[
            "provision_id"
        ]:
            rule

        for rule
        in classification_rules
    }

    selected_rules = [
        rules_by_id[
            rule_id
        ]
        for rule_id
        in decision.get(
            "rule_ids",
            [],
        )
    ]

    regulatory_basis = (
        get_medical_provisions(
            GENERAL_REGULATORY_BASIS_IDS,
            document_code=(
                MDR_DOCUMENT_CODE
            ),
        )
    )

    return {
        "status":
            status,

        "framework": {
            "document_code":
                MDR_DOCUMENT_CODE,

            "document_name":
                applicability_evidence[
                    0
                ][
                    "document_name"
                ],
        },

        "medical_device":
            True,

        "classification":
            decision.get(
                "classification"
            ),

        "possible_classes":
            decision.get(
                "possible_classes",
                [],
            ),

        "rules": [
            public_source(
                rule
            )
            for rule
            in selected_rules
        ],

        "reason":
            decision.get(
                "reason"
            ),

        "missing_information":
            decision.get(
                "missing_information",
                [],
            ),

        "applicability_basis": [
            public_source(
                provision
            )
            for provision
            in applicability_evidence
        ],

        "regulatory_basis": [
            public_source(
                provision
            )
            for provision
            in regulatory_basis
        ],
    }
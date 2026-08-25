from regulatory_engine.fta.config import (
    load_fta_config,
)
from regulatory_engine.fta.tariff_classifier import (
    classify_fta_tariff_line,
)
from regulatory_engine.repositories.fta_repository import (
    find_legal_basis,
    find_origin_rule,
)


def normalize_country(value):
    if not value:
        return None

    return str(
        value
    ).strip().lower()


def find_applicable_agreement(
    exporter_country: str,
    importer_country: str,
):
    """
    Find an applicable agreement using the
    configured agreements supported by the corpus.
    """

    exporter = normalize_country(
        exporter_country
    )

    importer = normalize_country(
        importer_country
    )

    if not exporter or not importer:
        return None

    fta_config = load_fta_config()

    for (
        agreement_key,
        config,
    ) in fta_config.items():

        configured_exporter = (
            normalize_country(
                config[
                    "exporter_country"
                ]
            )
        )

        configured_importer = (
            normalize_country(
                config[
                    "importer_country"
                ]
            )
        )

        if (
            exporter == configured_exporter
            and importer == configured_importer
        ):
            return {
                "agreement_key":
                    agreement_key,

                "agreement_code":
                    config[
                        "agreement_code"
                    ],

                "agreement_name":
                    config[
                        "agreement_name"
                    ],

                "exporter_country":
                    config[
                        "exporter_country"
                    ],

                "importer_region":
                    config[
                        "importer_region"
                    ],
            }

    return None


def find_tariff_schedule_line(
    agreement_key: str,
    agreement_code: str,
    nc_code: str,
    product_description: str | None,
    current_nc_description: str | None,
):
    """
    Reconcile current NC nomenclature with the
    historical nomenclature used by an FTA when
    that agreement requires this step.
    """

    fta_config = load_fta_config()

    agreement_config = fta_config[
        agreement_key
    ]

    if (
        "tariff_schedule"
        not in agreement_config
    ):
        return None

    if not product_description:
        return {
            "status":
                "NOT_EVALUATED",

            "reason": (
                "La description du produit "
                "est nécessaire pour rapprocher "
                "la nomenclature NC actuelle "
                "de la nomenclature historique "
                "de l'accord."
            ),
        }

    result = classify_fta_tariff_line(
        agreement_code=(
            agreement_code
        ),
        nc_code=(
            nc_code
        ),
        product_description=(
            product_description
        ),
        current_nc_description=(
            current_nc_description
        ),
        limit=5,
    )

    status = result[
        "status"
    ]

    if status != "SUPPORTED":
        return {
            "status":
                status,

            "reason":
                result.get(
                    "reason"
                ),
        }

    candidate = result[
        "candidate"
    ]

    return {
        "status":
            "SUPPORTED",

        "tariff_code":
            candidate[
                "tariff_code"
            ],

        "description":
            candidate[
                "description"
            ],

        "base_rate_pct":
            candidate[
                "base_rate_pct"
            ],

        "base_rate_text":
            candidate[
                "base_rate_text"
            ],

        "tariff_category":
            candidate[
                "tariff_category"
            ],

        "similarity":
            candidate[
                "similarity"
            ],

        "reason":
            result.get(
                "reason"
            ),

        "source_page":
            candidate[
                "source_page"
            ],

        "source_excerpt":
            candidate[
                "source_excerpt"
            ],
    }


def get_preferential_context(
    nc_code: str,
    exporter_country: str,
    importer_country: str,
    product_description: str | None = None,
    current_nc_description: str | None = None,
):
    """
    Build the complete FTA context for a product.

    Flow:

        exporter/importer
              ↓
        applicable agreement
              ↓
        legal basis
              ↓
        origin rule
              ↓
        historical tariff reconciliation
        when required
    """

    agreement = (
        find_applicable_agreement(
            exporter_country=(
                exporter_country
            ),
            importer_country=(
                importer_country
            ),
        )
    )

    if agreement is None:
        return None

    agreement_key = agreement[
        "agreement_key"
    ]

    agreement_code = agreement[
        "agreement_code"
    ]

    legal_basis = find_legal_basis(
        agreement_code
    )

    origin_rule = find_origin_rule(
        agreement_code=agreement_code,
        nc_code=nc_code,
    )

    tariff_schedule = (
        find_tariff_schedule_line(
            agreement_key=agreement_key,
            agreement_code=agreement_code,
            nc_code=nc_code,
            product_description=(
                product_description
            ),
            current_nc_description=(
                current_nc_description
            ),
        )
    )

    public_agreement = {
        key: value
        for key, value
        in agreement.items()
        if key != "agreement_key"
    }

    return {
        "agreement":
            public_agreement,

        "legal_basis":
            legal_basis,

        "origin_rule":
            origin_rule,

        "origin_verification": {
            "status":
                "NOT_VERIFIED",

            "reason": (
                "Le scénario indique le pays "
                "d'exportation, mais ne fournit "
                "pas les informations de "
                "fabrication et de valeur des "
                "matières nécessaires pour "
                "vérifier indépendamment la "
                "règle d'origine préférentielle."
            ),
        },

        "tariff_schedule":
            tariff_schedule,
    }
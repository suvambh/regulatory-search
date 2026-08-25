from dataclasses import asdict

from regulatory_engine.fta import (
    get_preferential_context,
)

from regulatory_engine.classification.service import (
    search_and_classify,
)
from regulatory_engine.models import ImportRequest
from regulatory_engine.tariff.calculator import (
    calculate_standard_tariff,
)


# ============================================================
# NC candidate helpers
# ============================================================


def find_selected_candidate_rate(
    candidates,
    nc_code,
):
    for row in candidates:
        candidate_nc_code = str(
            row[0]
        ).strip()

        if candidate_nc_code == nc_code:
            if row[2] is None:
                return None

            return float(
                row[2]
            )

    return None


def find_selected_candidate_description(
    candidates,
    nc_code,
):
    """
    Return the reconstructed NC2024 description
    for the selected candidate.
    """

    for row in candidates:
        candidate_nc_code = str(
            row[0]
        ).strip()

        if candidate_nc_code == nc_code:
            return row[1]

    return None


def find_common_candidate_context(
    candidates,
):
    """
    If all plausible candidates share:
        - the same HS4 heading
        - the same standard duty rate

    then the tariff can be calculated at that
    common level without claiming an exact NC8 code.
    """

    if not candidates:
        return None

    hs_codes = set()
    duty_rates = set()

    for row in candidates:
        nc_code = str(
            row[0]
        ).strip()

        if len(nc_code) < 4:
            return None

        hs_codes.add(
            nc_code[:4]
        )

        if row[2] is None:
            return None

        duty_rates.add(
            float(row[2])
        )

    if len(hs_codes) != 1:
        return None

    if len(duty_rates) != 1:
        return None

    return {
        "hs_code":
            next(iter(hs_codes)),

        "standard_rate_pct":
            next(iter(duty_rates)),
    }


# ============================================================
# Preferential tariff
# ============================================================


def determine_preferential_rate(
    fta_context,
):
    """
    Determine a preferential rate only when
    the ingested evidence directly supports it.

    Supported paths:

    1. Historical FTA tariff line explicitly
       states exemption.

    2. A legal provision directly states
       exemption from customs duties.

    Tariff dismantling categories are not
    interpreted here.
    """

    # --------------------------------------------------------
    # Historical tariff schedule
    # --------------------------------------------------------

    tariff_schedule = fta_context.get(
        "tariff_schedule"
    )

    if (
        tariff_schedule
        and tariff_schedule.get("status")
        == "SUPPORTED"
    ):
        base_rate_text = (
            tariff_schedule.get(
                "base_rate_text"
            )
            or ""
        ).strip().lower()

        base_rate_pct = tariff_schedule.get(
            "base_rate_pct"
        )

        if (
            base_rate_text == "exemption"
            and base_rate_pct is not None
            and float(base_rate_pct) == 0.0
        ):
            return {
                "rate_pct": 0.0,

                "derived_from": {
                    "type":
                        "FTA_TARIFF_SCHEDULE",

                    "tariff_code":
                        tariff_schedule.get(
                            "tariff_code"
                        ),

                    "base_rate_text":
                        tariff_schedule.get(
                            "base_rate_text"
                        ),

                    "tariff_category":
                        tariff_schedule.get(
                            "tariff_category"
                        ),

                    "source_page":
                        tariff_schedule.get(
                            "source_page"
                        ),

                    "source_excerpt":
                        tariff_schedule.get(
                            "source_excerpt"
                        ),
                },
            }

    # --------------------------------------------------------
    # Direct legal exemption
    # --------------------------------------------------------

    legal_basis = fta_context.get(
        "legal_basis",
        [],
    )

    for provision in legal_basis:
        text = (
            provision.get("text")
            or ""
        ).lower()

        if (
            "exemption de droits de douane"
            in text
        ):
            return {
                "rate_pct": 0.0,

                "derived_from": {
                    "type":
                        "LEGAL_PROVISION",

                    "article":
                        provision[
                            "article"
                        ],

                    "source_document":
                        provision[
                            "source_document"
                        ],

                    "source_page":
                        provision[
                            "source_page"
                        ],

                    "source_excerpt":
                        provision[
                            "source_excerpt"
                        ],
                },
            }

    return None


def build_preferential_tariff(
    scenario_input,
    lookup_code,
    standard_rate_pct,
    classification_status,
    product_description,
    current_nc_description=None,
):
    exporter_country = scenario_input[
        "export_country"
    ]

    importer_country = scenario_input[
        "import_country"
    ]

    # --------------------------------------------------------
    # Retrieve FTA context
    # --------------------------------------------------------

    fta_context = get_preferential_context(
        nc_code=lookup_code,
        exporter_country=exporter_country,
        importer_country=importer_country,
        product_description=(
            product_description
        ),
        current_nc_description=(
            current_nc_description
        ),
    )

    if fta_context is None:
        return {
            "status":
                "NO_SUPPORTED_AGREEMENT",

            "agreement":
                None,

            "preferential_rate_pct":
                None,

            "preferential_duty_eur":
                None,

            "saving_eur":
                None,
        }

    # --------------------------------------------------------
    # Determine rate
    # --------------------------------------------------------

    preferential_rule = (
        determine_preferential_rate(
            fta_context
        )
    )

    if preferential_rule is None:
        return {
            "status":
                "PREFERENCE_NOT_DETERMINED",

            "agreement":
                fta_context[
                    "agreement"
                ],

            "legal_basis":
                fta_context[
                    "legal_basis"
                ],

            "origin_rule":
                fta_context[
                    "origin_rule"
                ],

            "origin_verification":
                fta_context[
                    "origin_verification"
                ],

            "tariff_schedule":
                fta_context.get(
                    "tariff_schedule"
                ),

            "preferential_rate_pct":
                None,

            "preferential_duty_eur":
                None,

            "saving_eur":
                None,
        }

    # --------------------------------------------------------
    # Calculate preferential duty
    # --------------------------------------------------------

    goods_value_eur = float(
        scenario_input[
            "goods_value_eur"
        ]
    )

    preferential_rate_pct = (
        preferential_rule[
            "rate_pct"
        ]
    )

    preferential_duty_eur = round(
        goods_value_eur
        * preferential_rate_pct
        / 100,
        2,
    )

    standard_duty_eur = round(
        goods_value_eur
        * standard_rate_pct
        / 100,
        2,
    )

    saving_eur = round(
        standard_duty_eur
        - preferential_duty_eur,
        2,
    )

    if classification_status == "SUPPORTED":
        status = (
            "CALCULATED_ON_ASSERTED_ORIGIN"
        )
    else:
        status = (
            "CALCULATED_WITH_CLASSIFICATION_"
            "UNCERTAINTY_ON_ASSERTED_ORIGIN"
        )

    return {
        "status":
            status,

        "agreement":
            fta_context[
                "agreement"
            ],

        "standard_rate_pct":
            standard_rate_pct,

        "standard_duty_eur":
            standard_duty_eur,

        "preferential_rate_pct":
            preferential_rate_pct,

        "preferential_duty_eur":
            preferential_duty_eur,

        "saving_eur":
            saving_eur,

        "assumption": (
            f"The scenario states "
            f"{exporter_country} as the export "
            f"country. For the purpose of the "
            f"preferential tariff calculation, "
            f"the product is assumed to qualify "
            f"as originating under the applicable "
            f"agreement. This origin status cannot "
            f"be independently verified from the "
            f"scenario data provided."
        ),

        "origin_verification":
            fta_context[
                "origin_verification"
            ],

        "origin_rule":
            fta_context[
                "origin_rule"
            ],

        "legal_basis":
            fta_context[
                "legal_basis"
            ],

        "tariff_schedule":
            fta_context.get(
                "tariff_schedule"
            ),

        "preferential_rate_source":
            preferential_rule[
                "derived_from"
            ],
    }


# ============================================================
# Standard tariff with classification uncertainty
# ============================================================


def build_uncertain_standard_tariff(
    scenario_input,
    common_context,
    classification,
):
    goods_value_eur = float(
        scenario_input[
            "goods_value_eur"
        ]
    )

    rate = common_context[
        "standard_rate_pct"
    ]

    duty = round(
        goods_value_eur
        * rate
        / 100,
        2,
    )

    return {
        "status":
            "CALCULATED_WITH_CLASSIFICATION_UNCERTAINTY",

        "hs_code":
            common_context[
                "hs_code"
            ],

        "standard_rate_pct":
            rate,

        "standard_duty_eur":
            duty,

        "calculation_basis": (
            f"{goods_value_eur:.2f} EUR "
            f"× {rate}%"
        ),

        "classification_note": (
            "The exact 8-digit NC code could not be "
            "determined, but all retrieved plausible "
            "candidates share the same HS4 heading "
            "and standard duty rate."
        ),

        "missing_information":
            classification.get(
                "missing_information",
                [],
            ),
    }


# ============================================================
# Core evaluation
# ============================================================


def _evaluate_input(
    scenario_input,
):
    product = scenario_input[
        "product"
    ]

    # --------------------------------------------------------
    # 1. Retrieve + classify
    # --------------------------------------------------------

    search_result = search_and_classify(
        product,
        limit=5,
    )

    classification = search_result[
        "classification"
    ]

    candidates = search_result[
        "candidates"
    ]

    tariff = None
    preferential_tariff = None

    # --------------------------------------------------------
    # 2A. Exact NC classification
    # --------------------------------------------------------

    if (
        classification[
            "status"
        ]
        == "SUPPORTED"
        and classification.get(
            "nc_code"
        )
    ):
        nc_code = classification[
            "nc_code"
        ]

        tariff_result = (
            calculate_standard_tariff(
                nc_code=nc_code,
                goods_value_eur=(
                    scenario_input[
                        "goods_value_eur"
                    ]
                ),
            )
        )

        tariff = asdict(
            tariff_result
        )

        standard_rate_pct = (
            find_selected_candidate_rate(
                candidates=candidates,
                nc_code=nc_code,
            )
        )

        current_nc_description = (
            find_selected_candidate_description(
                candidates=candidates,
                nc_code=nc_code,
            )
        )

        if standard_rate_pct is not None:
            preferential_tariff = (
                build_preferential_tariff(
                    scenario_input=(
                        scenario_input
                    ),

                    lookup_code=(
                        nc_code
                    ),

                    standard_rate_pct=(
                        standard_rate_pct
                    ),

                    classification_status=(
                        classification[
                            "status"
                        ]
                    ),

                    product_description=(
                        product
                    ),

                    current_nc_description=(
                        current_nc_description
                    ),
                )
            )

    # --------------------------------------------------------
    # 2B. Exact NC uncertain, common HS4 + rate available
    # --------------------------------------------------------

    elif (
        classification[
            "status"
        ]
        == "UNCERTAIN_CLASSIFICATION"
    ):
        common_context = (
            find_common_candidate_context(
                candidates
            )
        )

        if common_context is not None:
            tariff = (
                build_uncertain_standard_tariff(
                    scenario_input=(
                        scenario_input
                    ),

                    common_context=(
                        common_context
                    ),

                    classification=(
                        classification
                    ),
                )
            )

            preferential_tariff = (
                build_preferential_tariff(
                    scenario_input=(
                        scenario_input
                    ),

                    lookup_code=(
                        common_context[
                            "hs_code"
                        ]
                    ),

                    standard_rate_pct=(
                        common_context[
                            "standard_rate_pct"
                        ]
                    ),

                    classification_status=(
                        classification[
                            "status"
                        ]
                    ),

                    product_description=(
                        product
                    ),

                    current_nc_description=None,
                )
            )

    return {
        "classification":
            classification,

        "tariff":
            tariff,

        "preferential_tariff":
            preferential_tariff,

        "candidates": [
            {
                "nc_code":
                    row[0],

                "description":
                    row[1],

                "duty_rate": (
                    float(row[2])
                    if row[2] is not None
                    else None
                ),

                "similarity":
                    float(row[3]),
            }
            for row in candidates
        ],
    }


# ============================================================
# Public application interface
# ============================================================


def evaluate_import(
    request: ImportRequest,
):
    """
    Main public interface of the regulatory engine.

    User-facing field names follow the terminology
    of the interview problem statement.
    """

    scenario_input = {
        "product":
            request.produit,

        "export_country":
            request.pays_exportateur,

        "import_country":
            request.pays_importateur,

        "goods_value_eur":
            request.valeur_marchandise_eur,
    }

    result = _evaluate_input(
        scenario_input
    )

    return {
        "input": {
            "produit":
                request.produit,

            "pays_exportateur":
                request.pays_exportateur,

            "pays_importateur":
                request.pays_importateur,

            "valeur_marchandise_eur":
                request.valeur_marchandise_eur,
        },

        **result,
    }
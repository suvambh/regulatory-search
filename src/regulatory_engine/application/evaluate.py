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
    """
    Return the standard duty rate attached to the
    selected exact NC8 candidate.
    """

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
    for the selected exact candidate.
    """

    for row in candidates:
        candidate_nc_code = str(
            row[0]
        ).strip()

        if candidate_nc_code == nc_code:
            return row[1]

    return None


def find_common_candidate_hs4(
    candidates,
):
    """
    Return a common HS4 heading when every retrieved
    plausible candidate belongs to the same HS4 family.

    Important:
    This helper deliberately DOES NOT infer a common
    customs-duty rate from semantic top-K candidates.

    The retrieved candidate set is not guaranteed to
    contain every legally plausible NC8 branch.
    """

    if not candidates:
        return None

    hs_codes = set()

    for row in candidates:
        nc_code = str(
            row[0]
        ).strip()

        if len(nc_code) < 4:
            return None

        hs_codes.add(
            nc_code[:4]
        )

    if len(hs_codes) != 1:
        return None

    return next(
        iter(hs_codes)
    )


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
    classification_status,
    product_description,
    current_nc_description=None,
    standard_rate_pct=None,
):
    """
    Retrieve preferential context and calculate only
    values that are supported by available evidence.

    standard_rate_pct may be None when exact NC8
    classification is unresolved.

    In that case:
        - preferential rate may still be determined
        - preferential duty may still be calculated
        - standard duty remains unknown
        - saving remains unknown
    """

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

            "standard_rate_pct":
                standard_rate_pct,

            "standard_duty_eur":
                None,

            "preferential_rate_pct":
                None,

            "preferential_duty_eur":
                None,

            "saving_eur":
                None,
        }

    # --------------------------------------------------------
    # Determine preferential rate
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

            "standard_rate_pct":
                standard_rate_pct,

            "standard_duty_eur":
                None,

            "preferential_rate_pct":
                None,

            "preferential_duty_eur":
                None,

            "saving_eur":
                None,
        }

    # --------------------------------------------------------
    # Preferential duty
    # --------------------------------------------------------

    goods_value_eur = float(
        scenario_input[
            "goods_value_eur"
        ]
    )

    preferential_rate_pct = float(
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

    # --------------------------------------------------------
    # Standard duty and saving
    #
    # These are calculated ONLY when an exact supported
    # standard rate is available.
    # --------------------------------------------------------

    standard_duty_eur = None
    saving_eur = None

    if standard_rate_pct is not None:
        standard_duty_eur = round(
            goods_value_eur
            * float(standard_rate_pct)
            / 100,
            2,
        )

        saving_eur = round(
            standard_duty_eur
            - preferential_duty_eur,
            2,
        )

    # --------------------------------------------------------
    # Result status
    # --------------------------------------------------------

    if (
        classification_status == "SUPPORTED"
        and standard_rate_pct is not None
    ):
        status = (
            "CALCULATED_ON_ASSERTED_ORIGIN"
        )

    else:
        status = (
            "PREFERENTIAL_RATE_DETERMINED_"
            "WITH_CLASSIFICATION_UNCERTAINTY_"
            "ON_ASSERTED_ORIGIN"
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
            f"preferential tariff assessment, "
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
    classification,
    hs_code,
):
    """
    Do not calculate a standard tariff from semantic
    top-K candidates when the exact NC8 classification
    is unresolved.

    Multiple NC8 branches within the same HS4 heading
    may carry different standard duty rates even when
    the retrieved top-K candidates happen to share one.
    """

    return {
        "status":
            "STANDARD_RATE_NOT_DETERMINED",

        "hs_code":
            hs_code,

        "standard_rate_pct":
            None,

        "standard_duty_eur":
            None,

        "calculation_basis":
            None,

        "classification_note": (
            "The product can be narrowed to a common "
            f"HS4 heading ({hs_code}), but the exact "
            "8-digit NC classification is unresolved. "
            "A standard customs-duty rate is therefore "
            "not calculated from the semantic candidate "
            "set because other NC8 branches within the "
            "same HS4 heading may carry different rates."
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
    # 2B. Exact NC uncertain
    #
    # A shared HS4 may still be useful for:
    #   - agreement lookup
    #   - origin-rule lookup
    #
    # It is NOT sufficient to derive a standard duty rate.
    # --------------------------------------------------------

    elif (
        classification[
            "status"
        ]
        == "UNCERTAIN_CLASSIFICATION"
    ):
        common_hs4 = (
            find_common_candidate_hs4(
                candidates
            )
        )

        if common_hs4 is not None:
            tariff = (
                build_uncertain_standard_tariff(
                    classification=(
                        classification
                    ),

                    hs_code=(
                        common_hs4
                    ),
                )
            )

            preferential_tariff = (
                build_preferential_tariff(
                    scenario_input=(
                        scenario_input
                    ),

                    lookup_code=(
                        common_hs4
                    ),

                    standard_rate_pct=None,

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

    # --------------------------------------------------------
    # Response
    # --------------------------------------------------------

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
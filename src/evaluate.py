import json
from dataclasses import asdict
from pathlib import Path

from fta import get_preferential_context
from regulatory_engine.models.requests import ImportRequest
from search import search_and_classify
from tariff import calculate_standard_tariff


SCENARIOS_PATH = Path(
    "data/evaluation/scenarios.json"
)

OUTPUT_DIR = Path(
    "data/evaluation/results"
)


# ============================================================
# Scenario utilities
# ============================================================


def load_scenarios():
    with open(
        SCENARIOS_PATH,
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def get_exporter_country(
    scenario_input,
):
    return (
        scenario_input.get("export_country")
        or scenario_input.get("exporter_country")
        or scenario_input.get("country_exporter")
        or scenario_input.get("pays_exportateur")
    )


def get_importer_country(
    scenario_input,
):
    return (
        scenario_input.get("import_country")
        or scenario_input.get("importer_country")
        or scenario_input.get("country_importer")
        or scenario_input.get("pays_importateur")
    )


# ============================================================
# NC candidate utilities
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
    Retrieve the reconstructed NC2024 description
    for the candidate selected by the classifier.

    This description is useful when reconciling
    the current nomenclature with an older FTA
    tariff schedule.
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
    If every plausible candidate has:
        - the same HS4 heading
        - the same standard duty rate

    then we can still calculate the tariff at
    that common level without pretending that
    an exact 8-digit NC code was determined.
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
# Preferential tariff logic
# ============================================================


def determine_preferential_rate(
    fta_context,
):
    """
    Determine a preferential rate only when
    the ingested evidence directly supports it.

    Two currently supported paths:

    1. FTA tariff schedule:
       A reconciled historical tariff line
       explicitly states "exemption".

       This is used for the Korea scenario.

    2. Legal provision:
       The agreement itself explicitly states
       an exemption from customs duty.

       This is used for the Morocco scenario.

    We deliberately do NOT derive a current
    preferential rate from tariff-dismantling
    categories such as category 5.
    """

    # --------------------------------------------------------
    # 1. Product-specific tariff schedule
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

        base_rate_pct = (
            tariff_schedule.get(
                "base_rate_pct"
            )
        )

        if (
            base_rate_text == "exemption"
            and base_rate_pct is not None
            and float(base_rate_pct) == 0.0
        ):
            return {
                "rate_pct":
                    0.0,

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
    # 2. Direct legal exemption
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
                "rate_pct":
                    0.0,

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
    exporter_country = get_exporter_country(
        scenario_input
    )

    importer_country = get_importer_country(
        scenario_input
    )

    if (
        not exporter_country
        or not importer_country
    ):
        return None

    # --------------------------------------------------------
    # Retrieve complete FTA context
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
    # Determine preferential rate from supported evidence
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

    # --------------------------------------------------------
    # Result status
    # --------------------------------------------------------

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
# Core engine evaluation
# ============================================================


def _evaluate_input(
    scenario_input,
):
    """
    Internal engine entry point.

    Uses the existing internal field names:

        product
        export_country
        import_country
        goods_value_eur

    Public interfaces such as Streamlit should use
    evaluate_import() instead.
    """

    product = scenario_input[
        "product"
    ]

    # --------------------------------------------------------
    # 1. Retrieve NC2024 candidates + classify
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
    # 2A. Exact NC classification available
    # --------------------------------------------------------

    if (
        classification[
            "status"
        ]
        == "SUPPORTED"
        and classification[
            "nc_code"
        ]
    ):

        nc_code = classification[
            "nc_code"
        ]

        # ----------------------------------------------------
        # Standard NC2024 tariff
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Preferential tariff
        # ----------------------------------------------------

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
    # 2B. Exact NC uncertain, but candidates share HS4 + rate
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

    # --------------------------------------------------------
    # 3. Internal engine result
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
                    float(
                        row[2]
                    )
                    if row[2]
                    is not None
                    else None
                ),

                "similarity":
                    float(
                        row[3]
                    ),
            }
            for row
            in candidates
        ],
    }


# ============================================================
# Public application interface
# ============================================================


def evaluate_import(
    request: ImportRequest,
):
    """
    Public application entry point.

    This contract follows the terminology used in
    the interview problem statement.

    Streamlit and any future interface should call
    this function rather than the internal evaluator.
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


# ============================================================
# Evaluation scenario adapter
# ============================================================


def evaluate_scenario(
    scenario,
):
    """
    Adapter used by the supplied seven evaluation scenarios.

    The scenario files retain their existing internal format
    so that the refactor does not change current behavior.
    """

    scenario_input = scenario[
        "input"
    ]

    result = _evaluate_input(
        scenario_input
    )

    return {
        "scenario_id":
            scenario[
                "scenario_id"
            ],

        "name":
            scenario[
                "name"
            ],

        "input":
            scenario_input,

        **result,
    }


# ============================================================
# Result persistence
# ============================================================


def save_result(
    result,
):
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    scenario_id = result[
        "scenario_id"
    ]

    output_path = (
        OUTPUT_DIR
        / f"scenario_{scenario_id}.json"
    )

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            result,
            file,
            indent=2,
            ensure_ascii=False,
        )

    return output_path


# ============================================================
# Manual scenario runner
# ============================================================


def main():
    scenarios = load_scenarios()

    for scenario in scenarios:

        print(
            f"\n--- SCENARIO "
            f"{scenario['scenario_id']} ---"
        )

        print(
            scenario[
                "input"
            ][
                "product"
            ]
        )

        try:
            result = evaluate_scenario(
                scenario
            )

            output_path = save_result(
                result
            )

            print(
                json.dumps(
                    {
                        "classification":
                            result[
                                "classification"
                            ],

                        "tariff":
                            result[
                                "tariff"
                            ],

                        "preferential_tariff":
                            result[
                                "preferential_tariff"
                            ],
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )

            print(
                f"Saved to "
                f"{output_path}"
            )

        except Exception as exc:
            print(
                f"ERROR: {exc}"
            )


if __name__ == "__main__":
    main()
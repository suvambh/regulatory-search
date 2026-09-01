import json
from pathlib import Path

from regulatory_engine.application import (
    evaluate_import,
)
from regulatory_engine.models import (
    ImportRequest,
)


SCENARIOS_PATH = Path(
    "data/evaluation/scenarios.json"
)

OUTPUT_DIR = Path(
    "data/evaluation/results"
)


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


def get_product(
    scenario_input,
):
    return (
        scenario_input.get("product")
        or scenario_input.get("produit")
    )


def get_goods_value(
    scenario_input,
):
    value = (
        scenario_input.get(
            "goods_value_eur"
        )
    )

    if value is None:
        value = scenario_input.get(
            "valeur_marchandise_eur"
        )

    return value


def scenario_to_request(
    scenario,
):
    scenario_input = scenario[
        "input"
    ]

    return ImportRequest(
        produit=get_product(
            scenario_input
        ),

        pays_exportateur=(
            get_exporter_country(
                scenario_input
            )
        ),

        pays_importateur=(
            get_importer_country(
                scenario_input
            )
        ),

        valeur_marchandise_eur=(
            get_goods_value(
                scenario_input
            )
        ),
    )


def evaluate_scenario(
    scenario,
):
    """
    Run a supplied interview scenario through
    the same public application entry point that
    will later be used by Streamlit.
    """

    request = scenario_to_request(
        scenario
    )

    result = evaluate_import(
        request
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
            scenario[
                "input"
            ],

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

        "medical_regulation":
            result.get(
                "medical_regulation"
            ),

        "candidates":
            result[
                "candidates"
            ],
    }


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


def main():
    scenarios = load_scenarios()

    for scenario in scenarios:
        print(
            f"\n--- SCENARIO "
            f"{scenario['scenario_id']} ---"
        )

        print(
            get_product(
                scenario[
                    "input"
                ]
            )
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

                        "medical_regulation":
                            result[
                                "medical_regulation"
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
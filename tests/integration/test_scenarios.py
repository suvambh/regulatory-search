import json
from enum import Enum
from pathlib import Path

import pytest

from regulatory_engine.application import (
    evaluate_import,
)
from regulatory_engine.models import (
    ImportRequest,
)


SCENARIOS_PATH = Path(
    "data/evaluation/scenarios.json"
)

BASELINE_DIR = Path(
    "data/evaluation/results"
)


def load_scenarios():
    with SCENARIOS_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def scenario_to_request(
    scenario,
):
    data = scenario["input"]

    return ImportRequest(
        produit=(
            data.get("produit")
            or data.get("product")
        ),
        pays_exportateur=(
            data.get("pays_exportateur")
            or data.get("export_country")
            or data.get("exporter_country")
        ),
        pays_importateur=(
            data.get("pays_importateur")
            or data.get("import_country")
            or data.get("importer_country")
        ),
        valeur_marchandise_eur=(
            data.get("valeur_marchandise_eur")
            if data.get(
                "valeur_marchandise_eur"
            ) is not None
            else data.get(
                "goods_value_eur"
            )
        ),
    )


def load_baseline(
    scenario_id,
):
    path = (
        BASELINE_DIR
        / f"scenario_{scenario_id}.json"
    )

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def normalize_value(value):
    """
    Convert Enum values recursively so application
    dataclasses and JSON baselines compare cleanly.
    """

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, dict):
        return {
            key: normalize_value(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            normalize_value(item)
            for item in value
        ]

    return value


def stable_projection(
    result,
):
    """
    Keep only stable, business-relevant fields.

    We intentionally exclude:
    - LLM reason wording
    - vector similarity scores
    - candidate ranking details
    - long source excerpts

    Those can change without changing the
    regulatory answer.
    """

    result = normalize_value(
        result
    )

    classification = (
        result.get("classification")
        or {}
    )

    tariff = (
        result.get("tariff")
        or {}
    )

    preference = (
        result.get(
            "preferential_tariff"
        )
        or {}
    )

    agreement = (
        preference.get("agreement")
        or {}
    )

    origin_verification = (
        preference.get(
            "origin_verification"
        )
        or {}
    )

    origin_rule = (
        preference.get(
            "origin_rule"
        )
        or {}
    )

    tariff_schedule = (
        preference.get(
            "tariff_schedule"
        )
        or {}
    )

    return {
        "classification": {
            "status":
                classification.get(
                    "status"
                ),

            "nc_code":
                classification.get(
                    "nc_code"
                ),

            "missing_information":
                classification.get(
                    "missing_information",
                    [],
                ),
        },

        "tariff": {
            "status":
                tariff.get(
                    "status"
                ),

            "hs_code":
                tariff.get(
                    "hs_code"
                ),

            "standard_rate_pct":
                tariff.get(
                    "standard_rate_pct"
                ),

            "standard_duty_eur":
                tariff.get(
                    "standard_duty_eur"
                ),
        },

        "preference": {
            "status":
                preference.get(
                    "status"
                ),

            "preferential_rate_pct":
                preference.get(
                    "preferential_rate_pct"
                ),

            "preferential_duty_eur":
                preference.get(
                    "preferential_duty_eur"
                ),

            "saving_eur":
                preference.get(
                    "saving_eur"
                ),

            "agreement_code":
                agreement.get(
                    "agreement_code"
                ),

            "origin_verification_status":
                origin_verification.get(
                    "status"
                ),

            "origin_rule_hs_code":
                origin_rule.get(
                    "hs_code"
                ),

            "tariff_schedule_status":
                tariff_schedule.get(
                    "status"
                ),

            "tariff_schedule_code":
                tariff_schedule.get(
                    "tariff_code"
                ),
        },
    }


SCENARIOS = load_scenarios()


@pytest.mark.parametrize(
    "scenario",
    SCENARIOS,
    ids=[
        f"scenario_{scenario['scenario_id']}"
        for scenario in SCENARIOS
    ],
)
def test_scenario_regression(
    scenario,
):
    """
    Every supplied interview scenario must preserve
    the checked-in regulatory behavior unless a
    deliberate functional change is made.
    """

    scenario_id = scenario[
        "scenario_id"
    ]

    expected = load_baseline(
        scenario_id
    )

    request = scenario_to_request(
        scenario
    )

    actual = evaluate_import(
        request
    )

    assert stable_projection(
        actual
    ) == stable_projection(
        expected
    )


def test_all_seven_scenarios_are_present():
    ids = {
        scenario["scenario_id"]
        for scenario in SCENARIOS
    }

    assert ids == {
        1,
        2,
        3,
        4,
        5,
        6,
        7,
    }


@pytest.mark.parametrize(
    "scenario",
    SCENARIOS,
    ids=[
        f"scenario_{scenario['scenario_id']}"
        for scenario in SCENARIOS
    ],
)
def test_supported_nc_code_was_retrieved(
    scenario,
):
    """
    A SUPPORTED classification must always select
    a code that was actually retrieved.

    This prevents the LLM from inventing NC codes.
    """

    result = evaluate_import(
        scenario_to_request(
            scenario
        )
    )

    classification = result[
        "classification"
    ]

    if (
        classification["status"]
        != "SUPPORTED"
    ):
        return

    selected_code = classification[
        "nc_code"
    ]

    retrieved_codes = {
        str(candidate["nc_code"])
        for candidate
        in result["candidates"]
    }

    assert selected_code in retrieved_codes
import json
from pathlib import Path


RULES_PATH = Path(
    "data/regulatory/morocco_preferences.json"
)


def load_preference_rules(
    rules_path: Path = RULES_PATH,
):
    if not rules_path.exists():
        return None

    with rules_path.open(
        "r",
        encoding="utf-8",
    ) as f:
        return json.load(f)


def calculate_duty(
    value_eur: float,
    rate: float,
) -> float:
    return round(
        value_eur * rate / 100,
        2,
    )


def find_preference_rule(
    exporter: str,
    importer: str,
    heading_code: str,
):
    rules = load_preference_rules()

    if rules is None:
        return None

    for rule in rules:
        if (
            rule["exporter"].lower()
            == exporter.lower()
            and rule["importer"].lower()
            == importer.lower()
            and heading_code
            in rule.get("nc_headings", [])
        ):
            return rule

    return None


def evaluate_tariff_preference(
    *,
    classification: dict,
    value_eur: float,
    exporter: str,
    importer: str,
    preferential_origin_confirmed: bool = False,
):
    # --------------------------------------------------
    # 1. Check whether classification contains enough
    #    information for the preference layer.
    # --------------------------------------------------

    resolution = classification.get(
        "resolution"
    )

    heading_code = classification.get(
        "heading_code"
    )

    standard_rate = classification.get(
        "standard_duty_rate"
    )

    if (
        resolution == "unresolved"
        or heading_code is None
    ):
        return {
            "status": "not_evaluated",
            "reason": (
                "The NC heading could not be established "
                "reliably, so preferential tariff treatment "
                "cannot be evaluated."
            ),
        }

    # --------------------------------------------------
    # 2. We also need a reliable standard tariff
    #    to calculate customs duty and savings.
    # --------------------------------------------------

    if standard_rate is None:
        return {
            "status": "not_evaluated",
            "reason": (
                "The applicable standard NC tariff rate "
                "could not be established reliably."
            ),
        }

    standard_rate = float(
        standard_rate
    )

    standard_duty = calculate_duty(
        value_eur,
        standard_rate,
    )

    # --------------------------------------------------
    # 3. Check that the agreement corpus is available.
    # --------------------------------------------------

    rules = load_preference_rules()

    if rules is None:
        return {
            "status": "agreement_unavailable",
            "standard_rate": standard_rate,
            "preferential_rate": None,
            "applicable_rate": standard_rate,
            "standard_duty_eur": standard_duty,
            "applicable_duty_eur": standard_duty,
            "tariff_saving_eur": 0.0,
            "value_plus_customs_duty_eur": round(
                value_eur + standard_duty,
                2,
            ),
            "reason": (
                "Preferential tariff could not be "
                "determined because the agreement "
                "corpus is unavailable."
            ),
        }

    # --------------------------------------------------
    # 4. Search for a rule covering the resolved
    #    NC heading.
    # --------------------------------------------------

    rule = find_preference_rule(
        exporter=exporter,
        importer=importer,
        heading_code=heading_code,
    )

    if rule is None:
        return {
            "status": "not_established",
            "standard_rate": standard_rate,
            "preferential_rate": None,
            "applicable_rate": standard_rate,
            "standard_duty_eur": standard_duty,
            "applicable_duty_eur": standard_duty,
            "tariff_saving_eur": 0.0,
            "value_plus_customs_duty_eur": round(
                value_eur + standard_duty,
                2,
            ),
            "reason": (
                "No preferential tariff rule was "
                "established for this NC heading from "
                "the currently indexed agreement scope."
            ),
        }

    preferential_rate = float(
        rule["preferential_rate"]
    )

    # --------------------------------------------------
    # 5. Rule found, but preferential origin has not
    #    yet been verified.
    # --------------------------------------------------

    if (
        rule["requires_preferential_origin"]
        and not preferential_origin_confirmed
    ):
        return {
            "status": "conditional",
            "standard_rate": standard_rate,
            "preferential_rate": preferential_rate,
            "applicable_rate": standard_rate,
            "standard_duty_eur": standard_duty,
            "applicable_duty_eur": standard_duty,
            "tariff_saving_eur": 0.0,
            "value_plus_customs_duty_eur": round(
                value_eur + standard_duty,
                2,
            ),
            "reason": (
                "A preferential tariff rule was found, "
                "but preferential Moroccan origin has "
                "not yet been established."
            ),
            "source_document": (
                rule["source_document"]
            ),
            "source_section": (
                rule["source_section"]
            ),
            "source_page": (
                rule["source_page"]
            ),
            "source_excerpt": (
                rule["source_excerpt"]
            ),
        }

    # --------------------------------------------------
    # 6. Preference applies.
    # --------------------------------------------------

    applicable_duty = calculate_duty(
        value_eur,
        preferential_rate,
    )

    saving = round(
        standard_duty - applicable_duty,
        2,
    )

    return {
        "status": "found",
        "standard_rate": standard_rate,
        "preferential_rate": preferential_rate,
        "applicable_rate": preferential_rate,
        "standard_duty_eur": standard_duty,
        "applicable_duty_eur": applicable_duty,
        "tariff_saving_eur": saving,
        "value_plus_customs_duty_eur": round(
            value_eur + applicable_duty,
            2,
        ),
        "source_document": (
            rule["source_document"]
        ),
        "source_section": (
            rule["source_section"]
        ),
        "source_page": (
            rule["source_page"]
        ),
        "source_excerpt": (
            rule["source_excerpt"]
        ),
    }
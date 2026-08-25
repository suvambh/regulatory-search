import json
from pathlib import Path


CONFIG_PATH = Path(
    "config/fta_agreements.json"
)


def load_fta_config():

    with open(
        CONFIG_PATH,
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def get_agreement_config(
    agreement_key: str,
):

    config = load_fta_config()

    if agreement_key not in config:
        raise ValueError(
            f"Unknown agreement: "
            f"{agreement_key}"
        )

    return config[
        agreement_key
    ]
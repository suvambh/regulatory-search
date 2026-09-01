import json
from pathlib import Path


CONFIG_PATH = Path(
    "config/medical_regulations.json"
)


def load_medical_config() -> dict:
    """
    Load the configured medical regulations.
    """

    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Medical regulation configuration "
            f"not found: {CONFIG_PATH}"
        )

    with CONFIG_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def get_medical_regulation_config(
    regulation_key: str,
) -> dict:
    """
    Return one configured medical regulation.
    """

    config = load_medical_config()

    if regulation_key not in config:
        raise ValueError(
            f"Unknown medical regulation: "
            f"{regulation_key}"
        )

    regulation = config[
        regulation_key
    ]

    required_fields = {
        "document_code",
        "document_name",
        "pdf_path",
        "raw_dir",
        "clean_dir",
    }

    missing = (
        required_fields
        - regulation.keys()
    )

    if missing:
        raise ValueError(
            f"Medical regulation "
            f"{regulation_key} is missing "
            f"required fields: "
            f"{sorted(missing)}"
        )

    return regulation
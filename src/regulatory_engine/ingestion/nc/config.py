import json
from pathlib import Path


CONFIG_PATH = Path(
    "config/nc.json"
)


def load_nc_config() -> dict:
    """
    Load the NC ingestion manifest.
    """

    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"NC configuration not found: "
            f"{CONFIG_PATH}"
        )

    with CONFIG_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:

        config = json.load(
            file
        )

    required_fields = {
        "source_document",
        "pdf_path",
        "raw_dir",
        "clean_dir",
        "pages",
    }

    missing = (
        required_fields
        - config.keys()
    )

    if missing:
        raise ValueError(
            "NC configuration is missing "
            f"required fields: "
            f"{sorted(missing)}"
        )

    if not config[
        "pages"
    ]:
        raise ValueError(
            "NC configuration contains "
            "no pages."
        )

    return config
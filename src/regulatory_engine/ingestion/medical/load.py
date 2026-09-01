import argparse
import json
from pathlib import Path

from regulatory_engine.infrastructure.database import (
    connect_db,
)
from regulatory_engine.infrastructure.storage import (
    ensure_local_file,
)
from regulatory_engine.medical.config import (
    get_medical_regulation_config,
)


UPSERT_PROVISION_SQL = """
INSERT INTO medical_provisions (
    document_code,
    document_name,
    provision_id,
    provision_type,
    provision_code,
    title,
    text,
    device_class,
    source_section,
    source_page,
    source_excerpt
)
VALUES (
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s,
    %s
)
ON CONFLICT (
    document_code,
    provision_id
)
DO UPDATE SET
    document_name = EXCLUDED.document_name,
    provision_type = EXCLUDED.provision_type,
    provision_code = EXCLUDED.provision_code,
    title = EXCLUDED.title,
    text = EXCLUDED.text,
    device_class = EXCLUDED.device_class,
    source_section = EXCLUDED.source_section,
    source_page = EXCLUDED.source_page,
    source_excerpt = EXCLUDED.source_excerpt,
    updated_at = NOW()
"""


def load_provisions(
    json_path: Path,
) -> int:
    """
    Load cleaned medical provisions into PostgreSQL.

    Loading is idempotent:
    existing provisions are updated using
    (document_code, provision_id).
    """

    json_path = Path(
        ensure_local_file(
            json_path
        )
    )

    data = json.loads(
        json_path.read_text(
            encoding="utf-8"
        )
    )

    provisions = data.get(
        "provisions",
        []
    )

    if not provisions:
        raise ValueError(
            f"No medical provisions found in "
            f"{json_path}"
        )

    with connect_db() as conn:

        with conn.cursor() as cur:

            for provision in provisions:

                cur.execute(
                    UPSERT_PROVISION_SQL,
                    (
                        provision[
                            "document_code"
                        ],
                        provision[
                            "document_name"
                        ],
                        provision[
                            "provision_id"
                        ],
                        provision[
                            "provision_type"
                        ],
                        provision.get(
                            "provision_code"
                        ),
                        provision.get(
                            "title"
                        ),
                        provision[
                            "text"
                        ],

                        # Cleaner does not derive
                        # regulatory classifications.
                        provision.get(
                            "device_class"
                        ),

                        provision.get(
                            "source_section"
                        ),
                        provision[
                            "source_page"
                        ],
                        provision.get(
                            "source_excerpt"
                        ),
                    ),
                )

        conn.commit()

    print(
        f"Loaded {len(provisions)} "
        f"medical provisions."
    )

    return len(
        provisions
    )


def load_regulation(
    regulation_key: str = "medical_mdr",
) -> int:
    """
    Load the cleaned dataset for one configured
    medical regulation.
    """

    config = (
        get_medical_regulation_config(
            regulation_key
        )
    )

    json_path = (
        Path(
            config[
                "clean_dir"
            ]
        )
        / "provisions.json"
    )

    return load_provisions(
        json_path
    )


def main():

    parser = argparse.ArgumentParser(
        description=(
            "Load cleaned medical "
            "regulatory provisions."
        )
    )

    parser.add_argument(
        "--regulation",
        default="medical_mdr",
    )

    args = parser.parse_args()

    load_regulation(
        regulation_key=(
            args.regulation
        )
    )


if __name__ == "__main__":
    main()
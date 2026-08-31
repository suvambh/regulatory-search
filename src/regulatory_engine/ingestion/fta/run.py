import subprocess
import sys

from regulatory_engine.infrastructure.migrations import (
    run_migrations,
)


STEPS = [
    (
        "regulatory_engine.ingestion.fta.extract",
        ["all", "all"],
    ),
    (
        "regulatory_engine.ingestion.fta.extract_legal",
        ["all"],
    ),
    (
        "regulatory_engine.ingestion.fta.clean_legal",
        ["all"],
    ),
    (
        "regulatory_engine.ingestion.fta.clean_origin",
        ["all"],
    ),
    (
        "regulatory_engine.ingestion.fta.clean_tariff",
        ["korea"],
    ),
    (
        "regulatory_engine.ingestion.fta.load_legal",
        ["all"],
    ),
    (
        "regulatory_engine.ingestion.fta.load_origin",
        ["all"],
    ),
    (
        "regulatory_engine.ingestion.fta.load_tariff",
        ["korea"],
    ),
    (
        "regulatory_engine.ingestion.fta.embed_tariff",
        [],
    ),
]


def run_step(
    module_name: str,
    args: list[str],
):
    print(
        f"\n{'=' * 70}\n"
        f"RUNNING: {module_name}"
        f"{' ' + ' '.join(args) if args else ''}\n"
        f"{'=' * 70}\n",
        flush=True,
    )

    subprocess.run(
        [
            sys.executable,
            "-m",
            module_name,
            *args,
        ],
        check=True,
    )


def main():

    # ----------------------------------------
    # Ensure the database schema exists
    # before any load/embed step.
    # ----------------------------------------

    print(
        f"\n{'=' * 70}\n"
        "RUNNING: database migrations\n"
        f"{'=' * 70}\n",
        flush=True,
    )

    run_migrations()

    # ----------------------------------------
    # Run FTA ingestion stages
    # ----------------------------------------

    for module_name, args in STEPS:

        run_step(
            module_name,
            args,
        )

    print(
        "\nFTA ingestion pipeline completed.",
        flush=True,
    )


if __name__ == "__main__":
    main()
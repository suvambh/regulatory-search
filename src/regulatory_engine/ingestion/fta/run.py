from regulatory_engine.fta.config import (
    load_fta_config,
)
from regulatory_engine.infrastructure.migrations import (
    run_migrations,
)

from regulatory_engine.ingestion.fta.extract import (
    extract_all_for_agreement,
)
from regulatory_engine.ingestion.fta.extract_legal import (
    extract_agreement as extract_legal_agreement,
)

from regulatory_engine.ingestion.fta.clean_legal import (
    clean_agreement as clean_legal_agreement,
)
from regulatory_engine.ingestion.fta.clean_origin import (
    clean_agreement as clean_origin_agreement,
)
from regulatory_engine.ingestion.fta.clean_tariff import (
    clean_agreement as clean_tariff_agreement,
)

from regulatory_engine.ingestion.fta.load_legal import (
    load_agreement as load_legal_agreement,
)
from regulatory_engine.ingestion.fta.load_origin import (
    load_agreement as load_origin_agreement,
)
from regulatory_engine.ingestion.fta.load_tariff import (
    load_agreement as load_tariff_agreement,
)

from regulatory_engine.ingestion.fta.embed_tariff import (
    embed_tariff_lines,
)


def print_stage(
    name: str,
):
    print(
        f"\n{'=' * 70}\n"
        f"{name}\n"
        f"{'=' * 70}\n",
        flush=True,
    )


def main():

    fta_config = load_fta_config()

    agreement_keys = list(
        fta_config.keys()
    )

    # --------------------------------------------------------
    # 1. Database migrations
    # --------------------------------------------------------

    print_stage(
        "DATABASE MIGRATIONS"
    )

    run_migrations()

    # --------------------------------------------------------
    # 2. Extract structured FTA tables
    #
    # Currently:
    #   - origin rules
    #   - historical tariff schedules when configured
    # --------------------------------------------------------

    print_stage(
        "EXTRACT STRUCTURED FTA TABLES"
    )

    for agreement_key in agreement_keys:

        extract_all_for_agreement(
            agreement_key
        )

    # --------------------------------------------------------
    # 3. Extract legal text
    # --------------------------------------------------------

    print_stage(
        "EXTRACT FTA LEGAL TEXT"
    )

    for agreement_key in agreement_keys:

        extract_legal_agreement(
            agreement_key
        )

    # --------------------------------------------------------
    # 4. Clean legal provisions
    # --------------------------------------------------------

    print_stage(
        "CLEAN FTA LEGAL PROVISIONS"
    )

    for agreement_key in agreement_keys:

        clean_legal_agreement(
            agreement_key
        )

    # --------------------------------------------------------
    # 5. Clean origin rules
    # --------------------------------------------------------

    print_stage(
        "CLEAN FTA ORIGIN RULES"
    )

    for agreement_key in agreement_keys:

        clean_origin_agreement(
            agreement_key
        )

    # --------------------------------------------------------
    # 6. Clean historical tariff schedules
    #
    # Only agreements containing tariff_schedule
    # in config are processed.
    # --------------------------------------------------------

    print_stage(
        "CLEAN FTA TARIFF SCHEDULES"
    )

    for (
        agreement_key,
        agreement_config,
    ) in fta_config.items():

        if (
            "tariff_schedule"
            not in agreement_config
        ):
            continue

        clean_tariff_agreement(
            agreement_key
        )

    # --------------------------------------------------------
    # 7. Load legal provisions
    # --------------------------------------------------------

    print_stage(
        "LOAD FTA LEGAL PROVISIONS"
    )

    for agreement_key in agreement_keys:

        load_legal_agreement(
            agreement_key
        )

    # --------------------------------------------------------
    # 8. Load origin rules
    # --------------------------------------------------------

    print_stage(
        "LOAD FTA ORIGIN RULES"
    )

    for agreement_key in agreement_keys:

        load_origin_agreement(
            agreement_key
        )

    # --------------------------------------------------------
    # 9. Load historical tariff schedules
    # --------------------------------------------------------

    print_stage(
        "LOAD FTA TARIFF SCHEDULES"
    )

    for (
        agreement_key,
        agreement_config,
    ) in fta_config.items():

        if (
            "tariff_schedule"
            not in agreement_config
        ):
            continue

        load_tariff_agreement(
            agreement_key
        )

    # --------------------------------------------------------
    # 10. Embed historical tariff lines
    # --------------------------------------------------------

    print_stage(
        "EMBED FTA TARIFF LINES"
    )

    embed_tariff_lines()

    # --------------------------------------------------------
    # Complete
    # --------------------------------------------------------

    print(
        "\nFTA ingestion pipeline completed.",
        flush=True,
    )


if __name__ == "__main__":
    main()
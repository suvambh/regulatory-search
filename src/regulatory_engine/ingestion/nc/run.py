from pathlib import Path

from regulatory_engine.infrastructure.migrations import (
    run_migrations,
)
from regulatory_engine.ingestion.nc.clean import (
    clean_pages,
)
from regulatory_engine.ingestion.nc.config import (
    load_nc_config,
)
from regulatory_engine.ingestion.nc.embed import (
    embed_tariff_items,
)
from regulatory_engine.ingestion.nc.extract import (
    extract_pages,
)
from regulatory_engine.ingestion.nc.load import (
    load_csv_files,
)


def main():

    config = load_nc_config()

    pdf_path = Path(
        config[
            "pdf_path"
        ]
    )

    raw_dir = Path(
        config[
            "raw_dir"
        ]
    )

    cleaned_dir = Path(
        config[
            "clean_dir"
        ]
    )

    page_numbers = [
        int(page)
        for page
        in config[
            "pages"
        ]
    ]

    source_document = config[
        "source_document"
    ]

    # --------------------------------------------------------
    # Database
    # --------------------------------------------------------

    print(
        "\n--- DATABASE MIGRATIONS ---"
    )

    run_migrations()

    # --------------------------------------------------------
    # Extract
    # --------------------------------------------------------

    print(
        "\n--- EXTRACT ---"
    )

    extract_pages(
        pdf_path=pdf_path,
        page_numbers=page_numbers,
        output_dir=raw_dir,
    )

    # --------------------------------------------------------
    # Clean
    # --------------------------------------------------------

    print(
        "\n--- CLEAN ---"
    )

    cleaned_files = (
        clean_pages(
            page_numbers=(
                page_numbers
            ),
            input_dir=(
                raw_dir
            ),
            output_dir=(
                cleaned_dir
            ),
            source_document=(
                source_document
            ),
        )
    )

    # --------------------------------------------------------
    # Load
    # --------------------------------------------------------

    print(
        "\n--- LOAD ---"
    )

    load_csv_files(
        csv_paths=cleaned_files,
    )

    # --------------------------------------------------------
    # Embed
    # --------------------------------------------------------

    print(
        "\n--- EMBED ---"
    )

    embed_tariff_items()

    print(
        "\nPipeline completed"
    )


if __name__ == "__main__":
    main()
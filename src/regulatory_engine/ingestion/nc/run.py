from pathlib import Path

from regulatory_engine.ingestion.nc.clean import clean_pages
from regulatory_engine.ingestion.nc.embed import embed_tariff_items
from regulatory_engine.ingestion.nc.extract import extract_pages
from regulatory_engine.ingestion.nc.load import load_csv_files
from regulatory_engine.infrastructure.migrations import (
    run_migrations,
)
from regulatory_engine.settings import DATABASE_URL


PDF_PATH = Path(
    "corpus/nc2024.pdf"
)

RAW_DIR = Path(
    "data/raw/nc"
)

CLEANED_DIR = Path(
    "data/cleaned/nc"
)

SOURCE_DOCUMENT = (
    "Nomenclature combinée 2024"
)


PAGE_NUMBERS = [
    136,  # 1509 20 00 - extra virgin olive oil
    604,
    605,
    622,  # 8507 60 00 - lithium-ion accumulators
    629,
    630,
    631,
    641,
    642,
    677,  # 9018 19 10 - pulse oximeter
    678,  # 9021 31 00 - joint prostheses
]


def main():

    print(
        "\n--- DATABASE MIGRATIONS ---"
    )

    run_migrations()
 
    print("\n--- EXTRACT ---")

    extract_pages(
        pdf_path=PDF_PATH,
        page_numbers=PAGE_NUMBERS,
        output_dir=RAW_DIR,
    )

    print("\n--- CLEAN ---")

    cleaned_files = clean_pages(
        page_numbers=PAGE_NUMBERS,
        input_dir=RAW_DIR,
        output_dir=CLEANED_DIR,
        source_document=SOURCE_DOCUMENT,
    )

    print("\n--- LOAD ---")

    load_csv_files(
        csv_paths=cleaned_files,
        db_url=DATABASE_URL,
    )

    print("\n--- EMBED ---")

    embed_tariff_items(
        db_url=DATABASE_URL,
    )

    print("\nPipeline completed")


if __name__ == "__main__":
    main()
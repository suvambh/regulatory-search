from pathlib import Path

from clean import clean_pages
from embed import embed_tariff_items
from extract import extract_pages
from load import load_csv_files

""" 605,641,642,631,"""

PDF_PATH = Path(
    "corpus/nc2024.pdf"
)

RAW_DIR = Path(
    "data/raw"
)

CLEANED_DIR = Path(
    "data/cleaned"
)

DB_URL = (
    "postgresql://regulatory_app:"
    "local_dev_password@localhost:5433/regulatory"
)

SOURCE_DOCUMENT = (
    "Nomenclature combinée 2024"
)


def main():
    page_numbers = [
    136,  # 1509 20 00 - extra virgin olive oil
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


    print("\n--- EXTRACT ---")

    extract_pages(
        pdf_path=PDF_PATH,
        page_numbers=page_numbers,
        output_dir=RAW_DIR,
    )

    print("\n--- CLEAN ---")

    cleaned_files = clean_pages(
        page_numbers=page_numbers,
        input_dir=RAW_DIR,
        output_dir=CLEANED_DIR,
        source_document=SOURCE_DOCUMENT,
    )

    print("\n--- LOAD ---")

    load_csv_files(
        csv_paths=cleaned_files,
        db_url=DB_URL,
    )

    print("\n--- EMBED ---")

    embed_tariff_items(
        db_url=DB_URL,
    )

    print("\nPipeline completed")


if __name__ == "__main__":
    main()
from pathlib import Path
import argparse

import boto3
import pymupdf

from textractprettyprinter.t_pretty_print import (
    Pretty_Print_Table_Format,
    Textract_Pretty_Print,
    get_string,
)

from regulatory_engine.fta.config import (
    load_fta_config,
    get_agreement_config,
)
from regulatory_engine.infrastructure.storage import (
    ensure_local_file,
    persist_file,
    restore_cached_file,
)
from regulatory_engine.settings import (
    AWS_REGION,
)


textract = boto3.client(
    "textract",
    region_name=AWS_REGION,
)


TABLE_DATASET_TYPES = {
    "origin",
    "tariff_schedule",
}


def extract_fta_table_pages(
    pdf_path: Path,
    page_numbers: list[int],
    output_dir: Path,
) -> list[Path]:

    pdf_path = Path(
        pdf_path
    )

    output_dir = Path(
        output_dir
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ----------------------------------------
    # Determine expected output files first
    # ----------------------------------------

    output_paths = {
        page_number: (
            output_dir
            / f"page-{page_number}.csv"
        )
        for page_number in page_numbers
    }

    # ----------------------------------------
    # Restore any cached extracted pages
    #
    # Local file:
    # data/raw/...
    #
    # S3:
    # processed/raw/...
    # ----------------------------------------

    missing_pages = []

    for page_number in page_numbers:

        output_path = output_paths[
            page_number
        ]

        if restore_cached_file(
            output_path
        ):
            print(
                f"Using cached FTA table page: "
                f"{output_path}"
            )
            continue

        missing_pages.append(
            page_number
        )

    # ----------------------------------------
    # If everything was cached, we do not
    # need the source PDF or Textract.
    # ----------------------------------------

    if not missing_pages:

        print(
            "All requested FTA table pages "
            "were restored from cache."
        )

        return [
            output_paths[
                page_number
            ]
            for page_number
            in page_numbers
        ]

    # ----------------------------------------
    # At least one page must be extracted.
    #
    # Ensure the PDF exists locally.
    # If S3 is enabled and the local PDF
    # is missing, storage.py downloads it.
    # ----------------------------------------

    pdf_path = ensure_local_file(
        pdf_path
    )

    document = pymupdf.open(
        pdf_path
    )

    try:

        for page_number in missing_pages:

            if (
                page_number < 1
                or page_number > len(document)
            ):
                raise ValueError(
                    f"Invalid page {page_number}. "
                    f"PDF has {len(document)} pages."
                )

            page = document[
                page_number - 1
            ]

            pixmap = page.get_pixmap(
                matrix=pymupdf.Matrix(
                    2,
                    2,
                ),
                alpha=False,
            )

            image_bytes = pixmap.tobytes(
                "png"
            )

            print(
                f"Processing FTA table page "
                f"{page_number}"
            )

            response = (
                textract.analyze_document(
                    Document={
                        "Bytes": image_bytes,
                    },
                    FeatureTypes=[
                        "TABLES",
                    ],
                )
            )

            csv_text = get_string(
                textract_json=response,
                table_format=(
                    Pretty_Print_Table_Format.csv
                ),
                output_type=[
                    Textract_Pretty_Print.TABLES
                ],
            )

            output_path = output_paths[
                page_number
            ]

            output_path.write_text(
                csv_text,
                encoding="utf-8",
            )

            print(
                f"Saved: {output_path}"
            )

            # --------------------------------
            # Persist extracted artifact
            # to S3 when S3 is enabled.
            #
            # data/raw/...
            # →
            # processed/raw/...
            # --------------------------------

            persist_file(
                output_path
            )

    finally:

        document.close()

    return [
        output_paths[
            page_number
        ]
        for page_number
        in page_numbers
    ]


def extract_dataset(
    agreement_key: str,
    dataset_type: str,
):

    if dataset_type not in TABLE_DATASET_TYPES:
        raise ValueError(
            f"Unsupported table dataset: "
            f"{dataset_type}"
        )

    config = get_agreement_config(
        agreement_key
    )

    dataset_config = config.get(
        dataset_type
    )

    if dataset_config is None:
        raise ValueError(
            f"No {dataset_type} configured "
            f"for agreement: "
            f"{agreement_key}"
        )

    pdf_path = Path(
        config[
            "pdf_path"
        ]
    )

    page_numbers = dataset_config[
        "pages"
    ]

    output_dir = Path(
        dataset_config[
            "raw_dir"
        ]
    )

    print(
        f"\nExtracting FTA dataset: "
        f"{agreement_key} / "
        f"{dataset_type}"
    )

    print(
        f"PDF: {pdf_path}"
    )

    print(
        f"Pages: {page_numbers}"
    )

    return extract_fta_table_pages(
        pdf_path=pdf_path,
        page_numbers=page_numbers,
        output_dir=output_dir,
    )


def extract_all_for_agreement(
    agreement_key: str,
):

    config = get_agreement_config(
        agreement_key
    )

    for dataset_type in (
        TABLE_DATASET_TYPES
    ):

        if dataset_type not in config:
            continue

        extract_dataset(
            agreement_key=agreement_key,
            dataset_type=dataset_type,
        )


def main():

    fta_config = load_fta_config()

    parser = argparse.ArgumentParser(
        description=(
            "Extract configured structured "
            "FTA tables using AWS Textract."
        )
    )

    parser.add_argument(
        "agreement",
        choices=[
            *fta_config.keys(),
            "all",
        ],
        help=(
            "FTA agreement to extract, "
            "or 'all'."
        ),
    )

    parser.add_argument(
        "dataset_type",
        choices=[
            "origin",
            "tariff_schedule",
            "all",
        ],
        help=(
            "Structured FTA dataset "
            "to extract."
        ),
    )

    args = parser.parse_args()

    # ----------------------------------------
    # All agreements + all configured
    # structured datasets
    # ----------------------------------------

    if (
        args.agreement == "all"
        and args.dataset_type == "all"
    ):

        for agreement_key in (
            fta_config.keys()
        ):
            extract_all_for_agreement(
                agreement_key
            )

        return

    # ----------------------------------------
    # One agreement + all configured
    # structured datasets
    # ----------------------------------------

    if args.dataset_type == "all":

        extract_all_for_agreement(
            args.agreement
        )

        return

    # ----------------------------------------
    # All agreements supporting one
    # specific dataset
    # ----------------------------------------

    if args.agreement == "all":

        for (
            agreement_key,
            config,
        ) in fta_config.items():

            if (
                args.dataset_type
                not in config
            ):
                continue

            extract_dataset(
                agreement_key=(
                    agreement_key
                ),
                dataset_type=(
                    args.dataset_type
                ),
            )

        return

    # ----------------------------------------
    # One agreement + one dataset
    # ----------------------------------------

    extract_dataset(
        agreement_key=(
            args.agreement
        ),
        dataset_type=(
            args.dataset_type
        ),
    )


if __name__ == "__main__":
    main()
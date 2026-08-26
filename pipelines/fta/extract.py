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


textract = boto3.client(
    "textract",
    region_name="eu-west-3",
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

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"PDF not found: {pdf_path}"
        )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    document = pymupdf.open(
        pdf_path
    )

    output_files = []

    try:

        for page_number in page_numbers:

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
                matrix=pymupdf.Matrix(2, 2),
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

            output_path = (
                output_dir
                / f"page-{page_number}.csv"
            )

            output_path.write_text(
                csv_text,
                encoding="utf-8",
            )

            output_files.append(
                output_path
            )

            print(
                f"Saved: {output_path}"
            )

    finally:
        document.close()

    return output_files


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
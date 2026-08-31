from pathlib import Path

import boto3
import pymupdf

from textractprettyprinter.t_pretty_print import (
    Pretty_Print_Table_Format,
    Textract_Pretty_Print,
    get_string,
)

from regulatory_engine.infrastructure.storage import (
    ensure_local_file,
    persist_file,
    restore_cached_file,
)
from regulatory_engine.settings import AWS_REGION


textract = boto3.client(
    "textract",
    region_name=AWS_REGION,
)


def extract_pages(
    pdf_path: Path,
    page_numbers: list[int],
    output_dir: Path,
) -> list[Path]:

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ----------------------------------------
    # Determine expected output files first.
    # ----------------------------------------

    output_files = [
        output_dir / f"page-{page_number}.csv"
        for page_number in page_numbers
    ]

    missing_pages = []

    # ----------------------------------------
    # Reuse local/S3 cached extraction
    # whenever possible.
    # ----------------------------------------

    for page_number, output_path in zip(
        page_numbers,
        output_files,
    ):

        if restore_cached_file(
            output_path
        ):
            print(
                f"Using cached extraction: "
                f"{output_path}"
            )
            continue

        missing_pages.append(
            (
                page_number,
                output_path,
            )
        )

    # Everything was already available.
    # We do not even need the PDF.
    if not missing_pages:

        print(
            "All requested NC pages "
            "were restored from cache."
        )

        return output_files

    # ----------------------------------------
    # At least one page requires Textract.
    #
    # Ensure the source PDF exists locally.
    # In S3 mode this downloads it when needed.
    # ----------------------------------------

    pdf_path = ensure_local_file(
        pdf_path
    )

    print(
        f"Using NC source PDF: "
        f"{pdf_path}"
    )

    document = pymupdf.open(
        pdf_path
    )

    try:

        for (
            page_number,
            output_path,
        ) in missing_pages:

            if (
                page_number < 1
                or page_number > len(document)
            ):
                raise ValueError(
                    f"Invalid page "
                    f"{page_number}. "
                    f"PDF has "
                    f"{len(document)} pages."
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

            image_bytes = (
                pixmap.tobytes(
                    "png"
                )
            )

            print(
                f"Processing NC page "
                f"{page_number}"
            )

            print(
                f"Image size: "
                f"{len(image_bytes) / 1024 / 1024:.2f} MB"
            )

            response = (
                textract.analyze_document(
                    Document={
                        "Bytes":
                            image_bytes,
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

            output_path.write_text(
                csv_text,
                encoding="utf-8",
            )

            print(
                f"Saved locally: "
                f"{output_path}"
            )

            # Persist the Textract result to
            # S3 when S3 mode is enabled.
            persist_file(
                output_path
            )

    finally:
        document.close()

    return output_files
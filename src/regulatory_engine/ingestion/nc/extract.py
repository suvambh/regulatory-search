from pathlib import Path

import boto3
import pymupdf

from textractprettyprinter.t_pretty_print import (
    Pretty_Print_Table_Format,
    Textract_Pretty_Print,
    get_string,
)


textract = boto3.client(
    "textract",
    region_name="eu-west-3",
)


def extract_pages(
    pdf_path: Path,
    page_numbers: list[int],
    output_dir: Path,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    document = pymupdf.open(pdf_path)

    output_files = []

    for page_number in page_numbers:
        page = document[page_number - 1]

        pixmap = page.get_pixmap(
            matrix=pymupdf.Matrix(2, 2),
            alpha=False,
        )

        image_bytes = pixmap.tobytes("png")

        print(f"Processing page {page_number}")
        print(
            f"Image size: "
            f"{len(image_bytes) / 1024 / 1024:.2f} MB"
        )

        response = textract.analyze_document(
            Document={
                "Bytes": image_bytes,
            },
            FeatureTypes=[
                "TABLES",
            ],
        )

        csv_text = get_string(
            textract_json=response,
            table_format=Pretty_Print_Table_Format.csv,
            output_type=[Textract_Pretty_Print.TABLES],
        )

        output_path = output_dir / f"page-{page_number}.csv"

        output_path.write_text(
            csv_text,
            encoding="utf-8",
        )

        output_files.append(output_path)

        print(f"Saved: {output_path}")

    document.close()

    return output_files
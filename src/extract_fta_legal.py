from pathlib import Path
import argparse

import boto3
import pymupdf

from fta_config import (
    load_fta_config,
    get_agreement_config,
)


textract = boto3.client(
    "textract",
    region_name="eu-west-3",
)


def extract_page_lines(
    pdf_path: Path,
    page_number: int,
) -> list[dict]:

    document = pymupdf.open(
        pdf_path
    )

    try:
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

    finally:
        document.close()

    response = (
        textract.detect_document_text(
            Document={
                "Bytes": image_bytes,
            }
        )
    )

    lines = []

    for block in response[
        "Blocks"
    ]:

        if (
            block["BlockType"]
            != "LINE"
        ):
            continue

        bounding_box = block[
            "Geometry"
        ][
            "BoundingBox"
        ]

        lines.append(
            {
                "text":
                    block["Text"],

                "left":
                    bounding_box[
                        "Left"
                    ],

                "top":
                    bounding_box[
                        "Top"
                    ],

                "width":
                    bounding_box[
                        "Width"
                    ],

                "height":
                    bounding_box[
                        "Height"
                    ],
            }
        )

    return lines


def order_two_column_page(
    lines: list[dict],
) -> list[dict]:

    left_column = []
    right_column = []

    for line in lines:

        if line["left"] < 0.5:
            left_column.append(
                line
            )
        else:
            right_column.append(
                line
            )

    left_column.sort(
        key=lambda line: (
            line["top"],
            line["left"],
        )
    )

    right_column.sort(
        key=lambda line: (
            line["top"],
            line["left"],
        )
    )

    return (
        left_column
        + right_column
    )


def lines_to_text(
    lines: list[dict],
) -> str:

    return "\n".join(
        line["text"]
        for line in lines
    )


def extract_page_text(
    pdf_path: Path,
    page_number: int,
) -> str:

    lines = extract_page_lines(
        pdf_path=pdf_path,
        page_number=page_number,
    )

    ordered_lines = (
        order_two_column_page(
            lines
        )
    )

    return lines_to_text(
        ordered_lines
    )


def extract_legal_pages(
    pdf_path: Path,
    page_numbers: list[int],
    output_dir: Path,
):

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"PDF not found: "
            f"{pdf_path}"
        )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    for page_number in page_numbers:

        print(
            f"Processing legal page "
            f"{page_number}"
        )

        text = extract_page_text(
            pdf_path=pdf_path,
            page_number=page_number,
        )

        output_path = (
            output_dir
            / f"page-{page_number}.txt"
        )

        output_path.write_text(
            text,
            encoding="utf-8",
        )

        print(
            f"Saved: {output_path}"
        )


def extract_agreement(
    agreement_key: str,
):

    config = get_agreement_config(
        agreement_key
    )

    legal_config = config[
        "legal"
    ]

    pdf_path = Path(
        config[
            "pdf_path"
        ]
    )

    page_numbers = (
        legal_config[
            "pages"
        ]
    )

    output_dir = Path(
        legal_config[
            "raw_dir"
        ]
    )

    print(
        f"\nExtracting FTA legal pages: "
        f"{agreement_key}"
    )

    print(
        f"PDF: {pdf_path}"
    )

    print(
        f"Pages: {page_numbers}"
    )

    extract_legal_pages(
        pdf_path=pdf_path,
        page_numbers=page_numbers,
        output_dir=output_dir,
    )


def main():

    fta_config = load_fta_config()

    parser = argparse.ArgumentParser(
        description=(
            "Extract configured FTA legal "
            "pages using AWS Textract."
        )
    )

    parser.add_argument(
        "agreement",
        choices=[
            *fta_config.keys(),
            "all",
        ],
    )

    args = parser.parse_args()

    if args.agreement == "all":

        for agreement_key in (
            fta_config.keys()
        ):
            extract_agreement(
                agreement_key
            )

    else:
        extract_agreement(
            args.agreement
        )


if __name__ == "__main__":
    main()
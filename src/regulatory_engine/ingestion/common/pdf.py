from pathlib import Path

import pymupdf

from textractprettyprinter.t_pretty_print import (
    Pretty_Print_Table_Format,
    Textract_Pretty_Print,
    get_string,
)

from regulatory_engine.infrastructure.textract import (
    get_textract_client,
)


def render_pdf_page(
    pdf_path: Path,
    page_number: int,
    scale: float = 2.0,
) -> bytes:
    """
    Render one 1-based PDF page to PNG bytes.
    """

    pdf_path = Path(
        pdf_path
    )

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
            matrix=pymupdf.Matrix(
                scale,
                scale,
            ),
            alpha=False,
        )

        return pixmap.tobytes(
            "png"
        )

    finally:
        document.close()


def extract_table_csv(
    image_bytes: bytes,
) -> str:
    """
    Extract tables from one rendered page
    and return CSV text.
    """

    textract = (
        get_textract_client()
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

    return get_string(
        textract_json=response,
        table_format=(
            Pretty_Print_Table_Format.csv
        ),
        output_type=[
            Textract_Pretty_Print.TABLES
        ],
    )


def extract_text(
    image_bytes: bytes,
) -> str:
    """
    Extract page text while preserving Textract's
    line ordering as returned by the service.
    """

    textract = (
        get_textract_client()
    )

    response = (
        textract.detect_document_text(
            Document={
                "Bytes":
                    image_bytes,
            }
        )
    )

    lines = []

    for block in response.get(
        "Blocks",
        [],
    ):
        if (
            block.get("BlockType")
            == "LINE"
        ):
            text = (
                block.get("Text")
                or ""
            ).strip()

            if text:
                lines.append(
                    text
                )

    return "\n".join(
        lines
    )
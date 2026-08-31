from pathlib import Path
import argparse

from regulatory_engine.fta.config import (
    load_fta_config,
    get_agreement_config,
)
from regulatory_engine.infrastructure.storage import (
    ensure_local_file,
    persist_file,
    restore_cached_file,
)
from regulatory_engine.infrastructure.textract import (
    get_textract_client,
)
from regulatory_engine.ingestion.common.pdf import (
    render_pdf_page,
)


def extract_page_lines(
    pdf_path: Path,
    page_number: int,
) -> list[dict]:
    """
    Extract Textract LINE blocks together with
    their geometry.

    Geometry is deliberately preserved because
    FTA legal pages may use two-column layouts.
    """

    image_bytes = (
        render_pdf_page(
            pdf_path=pdf_path,
            page_number=page_number,
        )
    )

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
            != "LINE"
        ):
            continue

        geometry = block.get(
            "Geometry",
            {},
        )

        bounding_box = (
            geometry.get(
                "BoundingBox",
                {},
            )
        )

        text = (
            block.get(
                "Text"
            )
            or ""
        ).strip()

        if not text:
            continue

        lines.append(
            {
                "text":
                    text,

                "left":
                    float(
                        bounding_box.get(
                            "Left",
                            0.0,
                        )
                    ),

                "top":
                    float(
                        bounding_box.get(
                            "Top",
                            0.0,
                        )
                    ),

                "width":
                    float(
                        bounding_box.get(
                            "Width",
                            0.0,
                        )
                    ),

                "height":
                    float(
                        bounding_box.get(
                            "Height",
                            0.0,
                        )
                    ),
            }
        )

    return lines


def order_two_column_page(
    lines: list[dict],
) -> list[dict]:
    """
    Reconstruct a simple two-column legal page.

    Lines whose left edge is in the first half
    of the page are read first, followed by the
    right-hand column.

    This intentionally preserves the behavior
    of the existing FTA legal extractor.
    """

    left_column = []
    right_column = []

    for line in lines:

        if line[
            "left"
        ] < 0.5:

            left_column.append(
                line
            )

        else:

            right_column.append(
                line
            )

    left_column.sort(
        key=lambda line: (
            line[
                "top"
            ],
            line[
                "left"
            ],
        )
    )

    right_column.sort(
        key=lambda line: (
            line[
                "top"
            ],
            line[
                "left"
            ],
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
        line[
            "text"
        ]
        for line
        in lines
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
    # Determine expected output files first.
    # ----------------------------------------

    output_paths = {
        page_number: (
            output_dir
            / f"page-{page_number}.txt"
        )
        for page_number
        in page_numbers
    }

    # ----------------------------------------
    # Restore cached legal-page text.
    #
    # Local:
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
                f"Using cached FTA legal page: "
                f"{output_path}"
            )
            continue

        missing_pages.append(
            page_number
        )

    # ----------------------------------------
    # Everything already exists locally
    # or was restored from S3.
    #
    # No PDF or Textract required.
    # ----------------------------------------

    if not missing_pages:

        print(
            "All requested FTA legal pages "
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
    # At least one page is missing.
    #
    # Download the PDF from S3 if the
    # local copy does not exist.
    # ----------------------------------------

    pdf_path = ensure_local_file(
        pdf_path
    )

    print(
        f"Using FTA legal source PDF: "
        f"{pdf_path}"
    )

    # ----------------------------------------
    # Extract only missing pages.
    # ----------------------------------------

    for page_number in missing_pages:

        print(
            f"Processing legal page "
            f"{page_number}"
        )

        text = extract_page_text(
            pdf_path=pdf_path,
            page_number=page_number,
        )

        output_path = output_paths[
            page_number
        ]

        output_path.write_text(
            text,
            encoding="utf-8",
        )

        print(
            f"Saved: {output_path}"
        )

        # ------------------------------------
        # Persist reusable Textract output
        # to S3.
        # ------------------------------------

        persist_file(
            output_path
        )

    return [
        output_paths[
            page_number
        ]
        for page_number
        in page_numbers
    ]


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

    return extract_legal_pages(
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
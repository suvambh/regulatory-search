from pathlib import Path

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
from regulatory_engine.medical.config import (
    get_medical_regulation_config,
)


def get_configured_pages(
    regulation_config: dict,
) -> list[int]:
    """
    Collect all page numbers declared in the
    regulation configuration.

    Pages can appear in more than one logical
    section, so duplicates are removed.
    """

    pages = set()

    for value in regulation_config.values():

        if not isinstance(
            value,
            dict,
        ):
            continue

        section_pages = value.get(
            "pages"
        )

        if not section_pages:
            continue

        for page_number in section_pages:
            pages.add(
                int(
                    page_number
                )
            )

    return sorted(
        pages
    )


def extract_page_lines(
    pdf_path: Path,
    page_number: int,
) -> list[dict]:
    """
    Extract Textract LINE blocks while retaining
    page geometry.

    Geometry is preserved because regulatory PDFs
    can use multi-column layouts.
    """

    image_bytes = render_pdf_page(
        pdf_path=pdf_path,
        page_number=page_number,
    )

    print(
        f"Processing medical page "
        f"{page_number}"
    )

    print(
        f"Image size: "
        f"{len(image_bytes) / 1024 / 1024:.2f} MB"
    )

    textract = get_textract_client()

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
            block.get(
                "BlockType"
            )
            != "LINE"
        ):
            continue

        geometry = block.get(
            "Geometry",
            {}
        )

        bounding_box = geometry.get(
            "BoundingBox",
            {}
        )

        text = block.get(
            "Text",
            ""
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


def order_page_lines(
    lines: list[dict],
) -> list[dict]:
    """
    Reconstruct reading order for the MDR pages.

    The source document can contain two-column
    legal text. Lines beginning in the left half
    are read first, followed by lines beginning
    in the right half.

    Geometry is kept separate from cleaning so
    that this extraction layer remains concerned
    only with document reconstruction.
    """

    left_column = [
        line
        for line in lines
        if line[
            "left"
        ] < 0.5
    ]

    right_column = [
        line
        for line in lines
        if line[
            "left"
        ] >= 0.5
    ]

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
    """
    Convert ordered Textract lines into page text.
    """

    return "\n".join(
        line[
            "text"
        ]
        for line in lines
    ).strip()


def extract_page_text(
    pdf_path: Path,
    page_number: int,
) -> str:

    lines = extract_page_lines(
        pdf_path=pdf_path,
        page_number=page_number,
    )

    ordered_lines = order_page_lines(
        lines
    )

    return lines_to_text(
        ordered_lines
    )


def extract_medical_pages(
    pdf_path: Path,
    page_numbers: list[int],
    output_dir: Path,
) -> list[Path]:
    """
    Extract configured medical regulation pages.

    Existing local/S3 extraction artifacts are
    restored and reused whenever possible.
    """

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_files = [
        output_dir
        / f"page-{page_number}.txt"

        for page_number
        in page_numbers
    ]

    missing_pages = []

    # --------------------------------------------------------
    # Restore existing extraction first.
    # --------------------------------------------------------

    for (
        page_number,
        output_path,
    ) in zip(
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

    # --------------------------------------------------------
    # Nothing requires Textract.
    # --------------------------------------------------------

    if not missing_pages:

        print(
            "All requested medical pages "
            "were restored from cache."
        )

        return output_files

    # --------------------------------------------------------
    # Ensure PDF exists locally only when extraction
    # is actually required.
    # --------------------------------------------------------

    pdf_path = Path(
        ensure_local_file(
            pdf_path
        )
    )

    print(
        f"Using medical source PDF: "
        f"{pdf_path}"
    )

    # --------------------------------------------------------
    # Extract missing pages.
    # --------------------------------------------------------

    for (
        page_number,
        output_path,
    ) in missing_pages:

        text = extract_page_text(
            pdf_path=pdf_path,
            page_number=page_number,
        )

        if not text:
            raise ValueError(
                f"Textract returned no text "
                f"for medical page "
                f"{page_number}."
            )

        output_path.write_text(
            text,
            encoding="utf-8",
        )

        print(
            f"Saved locally: "
            f"{output_path}"
        )

        persist_file(
            output_path
        )

    return output_files


def extract_regulation(
    regulation_key: str = "medical_mdr",
) -> list[Path]:
    """
    Extract all configured pages for one medical
    regulation.
    """

    config = (
        get_medical_regulation_config(
            regulation_key
        )
    )

    page_numbers = (
        get_configured_pages(
            config
        )
    )

    if not page_numbers:
        raise ValueError(
            f"No extraction pages configured "
            f"for {regulation_key}."
        )

    print(
        f"Extracting "
        f"{config['document_name']}"
    )

    print(
        f"Configured pages: "
        f"{page_numbers}"
    )

    return extract_medical_pages(
        pdf_path=Path(
            config[
                "pdf_path"
            ]
        ),
        page_numbers=page_numbers,
        output_dir=Path(
            config[
                "raw_dir"
            ]
        ),
    )


def main():

    outputs = extract_regulation()

    print(
        f"\nMedical extraction complete: "
        f"{len(outputs)} pages."
    )


if __name__ == "__main__":
    main()
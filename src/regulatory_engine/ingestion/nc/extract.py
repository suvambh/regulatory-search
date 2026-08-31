from pathlib import Path

from regulatory_engine.infrastructure.storage import (
    ensure_local_file,
    persist_file,
    restore_cached_file,
)
from regulatory_engine.ingestion.common.pdf import (
    extract_table_csv,
    render_pdf_page,
)


def extract_pages(
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

    output_files = [
        output_dir
        / f"page-{page_number}.csv"
        for page_number
        in page_numbers
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

    # ----------------------------------------
    # Everything was already available.
    #
    # We do not even need the PDF.
    # ----------------------------------------

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

    # ----------------------------------------
    # Extract only missing pages.
    # ----------------------------------------

    for (
        page_number,
        output_path,
    ) in missing_pages:

        print(
            f"Processing NC page "
            f"{page_number}"
        )

        image_bytes = (
            render_pdf_page(
                pdf_path=pdf_path,
                page_number=page_number,
            )
        )

        print(
            f"Image size: "
            f"{len(image_bytes) / 1024 / 1024:.2f} MB"
        )

        csv_text = (
            extract_table_csv(
                image_bytes
            )
        )

        output_path.write_text(
            csv_text,
            encoding="utf-8",
        )

        print(
            f"Saved locally: "
            f"{output_path}"
        )

        # ------------------------------------
        # Persist the Textract result to S3
        # when S3 mode is enabled.
        # ------------------------------------

        persist_file(
            output_path
        )

    return output_files
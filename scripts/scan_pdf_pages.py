from pathlib import Path
import argparse
import fitz  # PyMuPDF


DEFAULT_KEYWORDS = [
    "8528",
    "moniteur",
    "moniteurs",
    "écran",
    "écrans",
]


def search_pdf(
    pdf_path: Path,
    output_path: Path,
    keywords: list[str],
    start_page: int = 1,
    end_page: int = -1,
    context_lines: int = 3,
):
    document = fitz.open(pdf_path)

    total_pages = len(document)

    if end_page == -1:
        end_page = total_pages

    start_page = max(1, start_page)
    end_page = min(end_page, total_pages)

    results = []

    for pdf_page_number in range(start_page, end_page + 1):
        page = document[pdf_page_number - 1]

        text = page.get_text("text")

        lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip()
        ]

        for line_index, line in enumerate(lines):
            line_lower = line.lower()

            matched_keywords = [
                keyword
                for keyword in keywords
                if keyword.lower() in line_lower
            ]

            if not matched_keywords:
                continue

            start_context = max(
                0,
                line_index - context_lines,
            )

            end_context = min(
                len(lines),
                line_index + context_lines + 1,
            )

            context = lines[
                start_context:end_context
            ]

            results.append(
                {
                    "page": pdf_page_number,
                    "keywords": matched_keywords,
                    "context": context,
                }
            )

    document.close()

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as output_file:

        output_file.write(
            f"DOCUMENT: {pdf_path.name}\n"
        )
        output_file.write(
            f"SEARCH_PAGES: {start_page}-{end_page}\n"
        )
        output_file.write(
            f"KEYWORDS: {', '.join(keywords)}\n"
        )
        output_file.write(
            f"MATCHES: {len(results)}\n"
        )
        output_file.write("\n")

        for index, result in enumerate(
            results,
            start=1,
        ):
            output_file.write(
                f"=== MATCH {index} ===\n"
            )

            output_file.write(
                f"PDF_PAGE: {result['page']}\n"
            )

            output_file.write(
                "MATCHED_KEYWORDS: "
                + ", ".join(
                    result["keywords"]
                )
                + "\n"
            )

            output_file.write(
                "CONTEXT:\n"
            )

            for line in result["context"]:
                output_file.write(
                    f"{line}\n"
                )

            output_file.write("\n")

    print(f"Document: {pdf_path}")
    print(
        f"Pages searched: "
        f"{start_page}-{end_page}"
    )
    print(
        f"Matches found: {len(results)}"
    )
    print(f"Output: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Search PDF text for keywords "
            "and save matching pages/context."
        )
    )

    parser.add_argument(
        "pdf_path",
        type=Path,
        help="Path to PDF.",
    )

    parser.add_argument(
        "--keywords",
        nargs="+",
        default=DEFAULT_KEYWORDS,
        help=(
            "Keywords to search for. "
            "Default: 8528 moniteur moniteurs "
            "écran écrans"
        ),
    )

    parser.add_argument(
        "--start-page",
        type=int,
        default=1,
        help="First PDF page to search.",
    )

    parser.add_argument(
        "--end-page",
        type=int,
        default=-1,
        help=(
            "Last PDF page to search. "
            "-1 means last page."
        ),
    )

    parser.add_argument(
        "--context-lines",
        type=int,
        default=3,
        help=(
            "Number of surrounding lines "
            "to save around a match."
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output TXT path.",
    )

    args = parser.parse_args()

    pdf_path = args.pdf_path

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"PDF not found: {pdf_path}"
        )

    if args.output is None:
        output_path = (
            pdf_path.parent
            / f"{pdf_path.stem}_search.txt"
        )
    else:
        output_path = args.output

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    search_pdf(
        pdf_path=pdf_path,
        output_path=output_path,
        keywords=args.keywords,
        start_page=args.start_page,
        end_page=args.end_page,
        context_lines=args.context_lines,
    )


if __name__ == "__main__":
    main()
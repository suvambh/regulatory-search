from pathlib import Path
import re


PDF_PATH = Path("corpus/medical.pdf")

# How much text to print from each selected page.
MAX_CHARS_PER_PAGE = 1800

# Keywords useful for finding the parts of MDR that matter
# for the pulse oximeter and hip-prosthesis scenarios.
KEYWORDS = [
    "ANNEX VIII",
    "ANNEXE VIII",
    "CLASSIFICATION RULES",
    "RÈGLES DE CLASSIFICATION",
    "classification",
    "Rule 8",
    "Règle 8",
    "Rule 9",
    "Règle 9",
    "Rule 10",
    "Règle 10",
    "Rule 11",
    "Règle 11",
    "implantable",
    "implantable device",
    "active device",
    "dispositif actif",
    "diagnostic",
    "monitoring",
    "surveillance",
    "hip",
    "hanche",
    "joint replacement",
    "remplacement articulaire",
    "pulse oximeter",
    "oxymètre",
    "notified body",
    "organisme notifié",
    "conformity assessment",
    "évaluation de la conformité",
    "CE marking",
    "marquage CE",
]


def load_pdf_reader():
    """
    Prefer pypdf, but support PyPDF2 if that is already installed.
    """
    try:
        from pypdf import PdfReader
        return PdfReader(PDF_PATH)
    except ImportError:
        try:
            from PyPDF2 import PdfReader
            return PdfReader(PDF_PATH)
        except ImportError:
            raise SystemExit(
                "\nMissing PDF library.\n"
                "Install one with:\n\n"
                "    pip install pypdf\n"
            )


def clean_text(text: str) -> str:
    if not text:
        return ""

    # Normalize whitespace while keeping paragraphs reasonably readable.
    text = text.replace("\x00", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def extract_page(reader, page_index: int) -> str:
    try:
        text = reader.pages[page_index].extract_text() or ""
        return clean_text(text)
    except Exception as exc:
        return f"[PAGE EXTRACTION ERROR: {exc}]"


def print_page(page_number: int, text: str, reason: str = ""):
    print("\n" + "=" * 90)
    print(f"PDF PAGE: {page_number}")

    if reason:
        print(f"REASON: {reason}")

    print("-" * 90)

    if not text:
        print("[NO EXTRACTABLE TEXT]")
        return

    print(text[:MAX_CHARS_PER_PAGE])

    if len(text) > MAX_CHARS_PER_PAGE:
        print(
            f"\n...[truncated; full extracted page contains "
            f"{len(text):,} characters]"
        )


def main():
    if not PDF_PATH.exists():
        raise SystemExit(
            f"PDF not found: {PDF_PATH}\n"
            "Run this script from the project root."
        )

    reader = load_pdf_reader()
    page_count = len(reader.pages)

    print("=" * 90)
    print("MEDICAL PDF INSPECTION")
    print("=" * 90)
    print(f"File: {PDF_PATH}")
    print(f"Total PDF pages: {page_count}")

    print("\nExtracting page text...")
    page_texts = [
        extract_page(reader, i)
        for i in range(page_count)
    ]

    extractable_pages = sum(
        1 for text in page_texts
        if len(text.strip()) >= 40
    )

    print(
        f"Pages with extractable text: "
        f"{extractable_pages}/{page_count}"
    )

    if extractable_pages < page_count * 0.5:
        print(
            "\nWARNING: A large part of this PDF may be image/scanned content."
        )
        print(
            "If the important pages have no text, we can sample them "
            "with Textract instead."
        )

    # ------------------------------------------------------------------
    # 1. First pages
    # ------------------------------------------------------------------

    print("\n\n")
    print("#" * 90)
    print("1. DOCUMENT OPENING")
    print("#" * 90)

    for page_number in range(1, min(4, page_count + 1)):
        print_page(
            page_number,
            page_texts[page_number - 1],
            "document opening",
        )

    # ------------------------------------------------------------------
    # 2. Keyword discovery
    # ------------------------------------------------------------------

    print("\n\n")
    print("#" * 90)
    print("2. KEYWORD / REGULATORY SECTION DISCOVERY")
    print("#" * 90)

    matches_by_page = {}

    for index, text in enumerate(page_texts):
        if not text:
            continue

        lowered = text.casefold()

        hits = []

        for keyword in KEYWORDS:
            if keyword.casefold() in lowered:
                hits.append(keyword)

        if hits:
            matches_by_page[index + 1] = sorted(set(hits))

    if not matches_by_page:
        print("\nNo keyword matches were found.")
    else:
        print(
            f"\nPages containing relevant keywords: "
            f"{len(matches_by_page)}\n"
        )

        for page_number, hits in matches_by_page.items():
            print(
                f"Page {page_number:>4}: "
                + ", ".join(hits)
            )

    # ------------------------------------------------------------------
    # 3. Most useful candidate pages
    # ------------------------------------------------------------------

    print("\n\n")
    print("#" * 90)
    print("3. CANDIDATE MDR PAGES")
    print("#" * 90)

    # Prioritize pages mentioning Annex VIII / classification rules,
    # then specific rules and device concepts.
    priority_terms = [
        "annex viii",
        "annexe viii",
        "classification rules",
        "règles de classification",
        "rule 8",
        "règle 8",
        "rule 9",
        "règle 9",
        "rule 10",
        "règle 10",
        "rule 11",
        "règle 11",
        "joint replacement",
        "remplacement articulaire",
        "implantable",
        "monitoring",
        "surveillance",
    ]

    scored_pages = []

    for page_number, text in enumerate(page_texts, start=1):
        lowered = text.casefold()

        score = sum(
            1
            for term in priority_terms
            if term in lowered
        )

        if score:
            scored_pages.append(
                (score, page_number)
            )

    scored_pages.sort(
        key=lambda item: (-item[0], item[1])
    )

    # Keep output manageable.
    candidate_pages = [
        page_number
        for _, page_number in scored_pages[:15]
    ]

    if candidate_pages:
        for page_number in candidate_pages:
            hits = matches_by_page.get(page_number, [])

            print_page(
                page_number,
                page_texts[page_number - 1],
                reason=(
                    "candidate regulatory page"
                    + (
                        " | keywords: " + ", ".join(hits)
                        if hits
                        else ""
                    )
                ),
            )
    else:
        print("\nNo high-priority candidate pages were detected.")

    # ------------------------------------------------------------------
    # 4. Evenly spaced document samples
    # ------------------------------------------------------------------

    print("\n\n")
    print("#" * 90)
    print("4. EVENLY SPACED PDF SAMPLE")
    print("#" * 90)

    sample_count = min(8, page_count)

    if sample_count > 1:
        indexes = sorted(
            set(
                round(
                    i * (page_count - 1) / (sample_count - 1)
                )
                for i in range(sample_count)
            )
        )
    else:
        indexes = [0]

    for index in indexes:
        print_page(
            index + 1,
            page_texts[index],
            "evenly spaced sample",
        )

    # ------------------------------------------------------------------
    # 5. Summary for copying back into ChatGPT
    # ------------------------------------------------------------------

    print("\n\n")
    print("#" * 90)
    print("5. SUMMARY")
    print("#" * 90)

    print(f"\nTotal pages: {page_count}")
    print(f"Extractable pages: {extractable_pages}")

    print("\nTop candidate pages:")
    if candidate_pages:
        print(
            ", ".join(
                str(page)
                for page in candidate_pages
            )
        )
    else:
        print("None detected")

    annex_pages = []

    for page_number, text in enumerate(page_texts, start=1):
        lowered = text.casefold()

        if (
            "annex viii" in lowered
            or "annexe viii" in lowered
        ):
            annex_pages.append(page_number)

    print("\nPages mentioning Annex VIII:")
    if annex_pages:
        print(", ".join(map(str, annex_pages)))
    else:
        print("None detected")

    print(
        "\nPaste the output from sections "
        "2, 3 and 5 into the chat."
    )


if __name__ == "__main__":
    main()
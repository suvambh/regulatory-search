from pathlib import Path
from pypdf import PdfReader

PDF_PATH = Path("corpus/medical.pdf")
OUTPUT_PATH = Path("data/medical_mdr_relevant_pages.txt")

"""PAGES = [
    16,
    49, 50, 51, 52,
    108, 109, 110, 111, 112, 113,
    139, 140, 141, 142, 143, 144, 145,
    167, 168, 169, 170, 171,
]"""

PAGES = [
    32,33]

def main():
    reader = PdfReader(PDF_PATH)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        f.write("MDR ce SAMPLE\n")
        f.write("=" * 90 + "\n")

        for page_number in PAGES:
            if page_number < 1 or page_number > len(reader.pages):
                continue

            text = reader.pages[page_number - 1].extract_text() or ""

            f.write("\n\n")
            f.write("=" * 90 + "\n")
            f.write(f"PDF PAGE {page_number}\n")
            f.write("=" * 90 + "\n")
            f.write(text.strip())
            f.write("\n")

    print(f"Written to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
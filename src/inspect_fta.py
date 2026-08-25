from pathlib import Path
import re

import pymupdf


PDF_PATH = Path(
    "corpus/maroc.pdf"
)


PATTERNS = {
    "Article 7": re.compile(
        r"\bArticle\s+7\b",
        re.IGNORECASE,
    ),

    "Article 9": re.compile(
        r"\bArticle\s+9\b",
        re.IGNORECASE,
    ),

    "Article 29": re.compile(
        r"\bArticle\s+29\b",
        re.IGNORECASE,
    ),

    "Protocol 4": re.compile(
        r"\bProtocole\s+n?[°o]?\s*4\b",
        re.IGNORECASE,
    ),

    "Annex II": re.compile(
        r"\bAnnexe\s+II\b",
        re.IGNORECASE,
    ),

    "Industrial products": re.compile(
        r"\bProduits\s+industriels\b",
        re.IGNORECASE,
    ),

    "Originating products": re.compile(
        r"produits\s+originaires",
        re.IGNORECASE,
    ),

    "Origin rules list": re.compile(
        r"liste\s+des\s+ouvraisons",
        re.IGNORECASE,
    ),
}


def normalize_text(text):
    return " ".join(
        text.split()
    )


def main():

    document = pymupdf.open(
        PDF_PATH
    )

    for page_index, page in enumerate(document):

        page_number = page_index + 1

        text = page.get_text(
            "text",
            sort=True,
        )

        normalized = normalize_text(
            text
        )

        matches = []

        for name, pattern in PATTERNS.items():

            if pattern.search(normalized):
                matches.append(name)

        if matches:

            print(
                f"\n--- PDF PAGE "
                f"{page_number} ---"
            )

            print(
                "Matches:",
                ", ".join(matches),
            )

            print(
                normalized[:1500]
            )

    document.close()


if __name__ == "__main__":
    main()
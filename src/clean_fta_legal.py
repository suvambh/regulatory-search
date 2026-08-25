from pathlib import Path
import argparse
import re

import pandas as pd

from fta_config import (
    load_fta_config,
    get_agreement_config,
)


def normalize_text(value):
    return " ".join(
        str(value).split()
    ).strip()


def extract_article(
    text: str,
    article_number: str,
) -> str | None:
    """
    Extract one article from OCR text.

    Supports article numbers such as:
        Article 9
        Article 29
        Article 2.5

    Stops when the next article begins.
    """

    pattern = re.compile(
        rf"\bArticle\s+{re.escape(article_number)}\b"
        rf"(.*?)"
        rf"(?=\bArticle\s+\d+(?:\.\d+)?\b|\Z)",
        re.IGNORECASE | re.DOTALL,
    )

    match = pattern.search(
        text
    )

    if not match:
        return None

    return normalize_text(
        match.group(1)
    )


def build_chunk(
    config: dict,
    article: str,
    text: str,
    page: int,
    section: str,
):
    return {
        "agreement_code":
            config[
                "agreement_code"
            ],

        "agreement_name":
            config[
                "agreement_name"
            ],

        "exporter_country":
            config[
                "exporter_country"
            ],

        "importer_region":
            config[
                "importer_region"
            ],

        "chunk_type":
            "agreement_article",

        "article":
            article,

        "section":
            section,

        "text":
            text,

        "source_document":
            config[
                "source_document"
            ],

        "source_page":
            page,

        "source_excerpt":
            text,
    }


def clean_legal_articles(
    config: dict,
):

    legal_config = config[
        "legal"
    ]

    input_dir = Path(
        legal_config[
            "raw_dir"
        ]
    )

    output_path = Path(
        legal_config[
            "clean_path"
        ]
    )

    rows = []

    for article_config in legal_config[
        "articles"
    ]:

        article_number = str(
            article_config[
                "article"
            ]
        )

        page_number = int(
            article_config[
                "page"
            ]
        )

        section = (
            article_config[
                "section"
            ]
        )

        page_path = (
            input_dir
            / f"page-{page_number}.txt"
        )

        if not page_path.exists():
            raise FileNotFoundError(
                f"Legal page not found: "
                f"{page_path}"
            )

        page_text = (
            page_path.read_text(
                encoding="utf-8"
            )
        )

        article_text = extract_article(
            text=page_text,
            article_number=article_number,
        )

        if not article_text:
            raise ValueError(
                f"Article {article_number} "
                f"not found in {page_path}"
            )

        rows.append(
            build_chunk(
                config=config,
                article=article_number,
                text=article_text,
                page=page_number,
                section=section,
            )
        )

    df = pd.DataFrame(
        rows
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_csv(
        output_path,
        index=False,
    )

    print(
        f"Cleaned {len(df)} "
        f"FTA legal chunks"
    )

    print(
        f"Saved: {output_path}"
    )

    print()

    if not df.empty:
        print(
            df[
                [
                    "agreement_code",
                    "article",
                    "source_page",
                    "text",
                ]
            ].to_string(
                index=False
            )
        )

    return output_path


def clean_agreement(
    agreement_key: str,
):

    config = get_agreement_config(
        agreement_key
    )

    print(
        f"\nCleaning FTA legal articles: "
        f"{agreement_key}"
    )

    return clean_legal_articles(
        config=config
    )


def main():

    fta_config = load_fta_config()

    parser = argparse.ArgumentParser(
        description=(
            "Clean extracted FTA legal "
            "articles."
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
            clean_agreement(
                agreement_key
            )

    else:
        clean_agreement(
            args.agreement
        )


if __name__ == "__main__":
    main()
import argparse
import json
import re
from pathlib import Path

from regulatory_engine.infrastructure.storage import (
    ensure_local_file,
    persist_file,
    restore_cached_file,
)
from regulatory_engine.medical.config import (
    get_medical_regulation_config,
)


# ---------------------------------------------------------------------
# Basic text cleanup
# ---------------------------------------------------------------------


PAGE_FURNITURE = {
    "Journal officiel de l'Union européenne",
    "FR",
    "5.5.2017",
}


def clean_page_text(
    raw_text: str,
) -> str:
    """
    Remove PDF page furniture while preserving line
    boundaries used to identify legal structure.

    Raw extraction files are never modified.
    """

    # Join words split by PDF line wrapping:
    #
    # classifi-
    # cation
    #
    # -> classification
    raw_text = re.sub(
        r"(?<=[A-Za-zÀ-ÖØ-öø-ÿ])"
        r"-\n"
        r"(?=[a-zà-öø-ÿ])",
        "",
        raw_text,
    )

    lines = []

    for raw_line in raw_text.splitlines():

        line = raw_line.strip()

        if not line:
            continue

        if line in PAGE_FURNITURE:
            continue

        if re.fullmatch(
            r"L\s+117/\d+",
            line,
            flags=re.IGNORECASE,
        ):
            continue

        lines.append(
            line
        )

    return "\n".join(
        lines
    ).strip()


def normalize_provision_text(
    text: str,
) -> str:
    """
    Normalize extracted provision text for storage.

    The observed Textract OCR forms Ila / Ilb are
    normalized to the official class notation IIa / IIb.

    This changes only the cleaned artifact, never the
    raw page extraction.
    """

    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    text = re.sub(
        r"\bIla\b",
        "IIa",
        text,
    )

    text = re.sub(
        r"\bIlb\b",
        "IIb",
        text,
    )

    return text


# ---------------------------------------------------------------------
# Page loading
# ---------------------------------------------------------------------


def get_all_configured_pages(
    config: dict,
) -> list[int]:
    """
    Collect every page declared anywhere in the
    regulation configuration.
    """

    pages = set()

    for value in config.values():

        if not isinstance(
            value,
            dict,
        ):
            continue

        for page_number in value.get(
            "pages",
            [],
        ):
            pages.add(
                int(page_number)
            )

    return sorted(
        pages
    )


def load_page(
    input_dir: Path,
    page_number: int,
) -> str:

    page_path = (
        input_dir
        / f"page-{page_number}.txt"
    )

    page_path = Path(
        ensure_local_file(
            page_path
        )
    )

    return clean_page_text(
        page_path.read_text(
            encoding="utf-8"
        )
    )


def load_pages(
    input_dir: Path,
    page_numbers: list[int],
) -> dict[int, str]:

    return {
        page_number: load_page(
            input_dir=input_dir,
            page_number=page_number,
        )
        for page_number
        in page_numbers
    }


def join_pages(
    page_texts: dict[int, str],
    page_numbers: list[int],
) -> str:

    return "\n".join(
        page_texts[
            page_number
        ]
        for page_number
        in page_numbers
    )


# ---------------------------------------------------------------------
# Structural patterns
# ---------------------------------------------------------------------


ARTICLE_HEADER_RE = re.compile(
    r"(?im)^Article\s+(\d+)\s*$"
)


DEFINITION_HEADER_RE = re.compile(
    r"(?im)^(\d+)\)\s+[«\"]"
)


RULE_HEADER_RE = re.compile(
    r"(?im)^"
    r"(?:\d+\.\d+\.\s*)?"
    r"Règle\s+(\d+)"
    r"\s*$"
)


# ---------------------------------------------------------------------
# Provenance helpers
# ---------------------------------------------------------------------


def find_article_page(
    page_texts: dict[int, str],
    article_number: str,
) -> int:

    pattern = re.compile(
        rf"(?im)^Article\s+"
        rf"{re.escape(article_number)}"
        rf"\s*$"
    )

    for (
        page_number,
        text,
    ) in sorted(
        page_texts.items()
    ):

        if pattern.search(
            text
        ):
            return page_number

    raise ValueError(
        f"Could not locate Article "
        f"{article_number}."
    )


def find_rule_page(
    page_texts: dict[int, str],
    rule_number: int,
) -> int:

    pattern = re.compile(
        rf"(?im)^"
        rf"(?:\d+\.\d+\.\s*)?"
        rf"Règle\s+"
        rf"{rule_number}"
        rf"\s*$"
    )

    for (
        page_number,
        text,
    ) in sorted(
        page_texts.items()
    ):

        if pattern.search(
            text
        ):
            return page_number

    raise ValueError(
        f"Could not locate Rule "
        f"{rule_number}."
    )


def find_definition_page(
    page_texts: dict[int, str],
    definition_number: int,
) -> int:

    pattern = re.compile(
        rf"(?im)^"
        rf"{definition_number}"
        rf"\)\s+[«\"]"
    )

    for (
        page_number,
        text,
    ) in sorted(
        page_texts.items()
    ):

        if pattern.search(
            text
        ):
            return page_number

    raise ValueError(
        f"Could not locate definition "
        f"{definition_number}."
    )


# ---------------------------------------------------------------------
# Output record
# ---------------------------------------------------------------------


def build_provision(
    config: dict,
    *,
    provision_id: str,
    provision_type: str,
    provision_code: str | None,
    title: str,
    text: str,
    source_section: str,
    source_page: int,
) -> dict:
    """
    Create a purely structural regulatory record.

    No regulatory conclusion is added here.
    """

    cleaned_text = (
        normalize_provision_text(
            text
        )
    )

    return {
        "document_code":
            config[
                "document_code"
            ],

        "document_name":
            config[
                "document_name"
            ],

        "provision_id":
            provision_id,

        "provision_type":
            provision_type,

        "provision_code":
            provision_code,

        "title":
            title,

        "text":
            cleaned_text,

        "source_section":
            source_section,

        "source_page":
            source_page,

        "source_excerpt":
            cleaned_text,
    }


# ---------------------------------------------------------------------
# Definitions
# ---------------------------------------------------------------------


def get_article_2_text(
    text: str,
) -> str:
    """
    Restrict definition parsing to Article 2 when its
    heading is present.
    """

    article_2 = re.search(
        r"(?im)^Article\s+2\s*$",
        text,
    )

    if article_2 is None:
        return text

    next_article = re.search(
        r"(?im)^Article\s+3\s*$",
        text[
            article_2.end():
        ],
    )

    if next_article is None:
        return text[
            article_2.end():
        ]

    end = (
        article_2.end()
        + next_article.start()
    )

    return text[
        article_2.end():
        end
    ]


def extract_definitions(
    config: dict,
    page_texts: dict[int, str],
) -> list[dict]:
    """
    Discover numbered Article 2 definitions directly
    from the source text.

    Nothing here specifies which definitions are
    legally relevant to a scenario.
    """

    section = config[
        "definitions"
    ]

    pages = [
        int(page)
        for page
        in section[
            "pages"
        ]
    ]

    text = join_pages(
        page_texts,
        pages,
    )

    text = get_article_2_text(
        text
    )

    matches = list(
        DEFINITION_HEADER_RE.finditer(
            text
        )
    )

    provisions = []

    for index, match in enumerate(
        matches
    ):

        definition_number = int(
            match.group(1)
        )

        if (
            index + 1
            < len(matches)
        ):
            end = matches[
                index + 1
            ].start()

        else:
            end = len(
                text
            )

        definition_text = text[
            match.start():
            end
        ].strip()

        # Pull the defined term from the source itself.
        term_match = re.search(
            r"[«\"]([^»\"]+)[»\"]",
            definition_text,
        )

        if term_match:
            title = (
                "Définition — "
                + term_match.group(1)
            )
        else:
            title = (
                "Définition "
                f"{definition_number}"
            )

        source_page = (
            find_definition_page(
                page_texts,
                definition_number,
            )
        )

        provisions.append(
            build_provision(
                config,
                provision_id=(
                    "MDR_ARTICLE_2_"
                    f"DEFINITION_"
                    f"{definition_number}"
                ),
                provision_type=(
                    "definition"
                ),
                provision_code=str(
                    definition_number
                ),
                title=title,
                text=definition_text,
                source_section=(
                    "Article 2 — Définitions"
                ),
                source_page=(
                    source_page
                ),
            )
        )

    return provisions


# ---------------------------------------------------------------------
# Articles
# ---------------------------------------------------------------------


def extract_article_from_text(
    text: str,
    article_number: str,
) -> str | None:

    pattern = re.compile(
        rf"(?im)^Article\s+"
        rf"{re.escape(article_number)}"
        rf"\s*$"
    )

    match = pattern.search(
        text
    )

    if match is None:
        return None

    next_article = ARTICLE_HEADER_RE.search(
        text,
        match.end(),
    )

    if next_article is None:
        end = len(
            text
        )
    else:
        end = next_article.start()

    return text[
        match.start():
        end
    ].strip()


def article_title(
    article_text: str,
    article_number: str,
) -> str:
    """
    Obtain the title from the first non-empty line
    following the Article header.
    """

    lines = [
        line.strip()
        for line
        in article_text.splitlines()
        if line.strip()
    ]

    if len(lines) >= 2:
        return lines[
            1
        ]

    return (
        f"Article "
        f"{article_number}"
    )


def extract_configured_articles(
    config: dict,
    page_texts: dict[int, str],
) -> list[dict]:

    provisions = []

    seen = set()

    for (
        section_name,
        section,
    ) in config.items():

        if not isinstance(
            section,
            dict,
        ):
            continue

        articles = section.get(
            "articles"
        )

        pages = section.get(
            "pages"
        )

        if not articles or not pages:
            continue

        joined_text = join_pages(
            page_texts,
            [
                int(page)
                for page
                in pages
            ],
        )

        for article_number in articles:

            article_number = str(
                article_number
            )

            if article_number in seen:
                continue

            article_text = (
                extract_article_from_text(
                    joined_text,
                    article_number,
                )
            )

            if not article_text:
                raise ValueError(
                    f"Configured MDR Article "
                    f"{article_number} "
                    f"was not found."
                )

            provisions.append(
                build_provision(
                    config,
                    provision_id=(
                        "MDR_ARTICLE_"
                        f"{article_number}"
                    ),
                    provision_type=(
                        "article"
                    ),
                    provision_code=(
                        article_number
                    ),
                    title=(
                        article_title(
                            article_text,
                            article_number,
                        )
                    ),
                    text=article_text,
                    source_section=(
                        f"Article "
                        f"{article_number}"
                    ),
                    source_page=(
                        find_article_page(
                            page_texts,
                            article_number,
                        )
                    ),
                )
            )

            seen.add(
                article_number
            )

    return provisions


# ---------------------------------------------------------------------
# Annex VIII classification rules
# ---------------------------------------------------------------------


def extract_classification_rules(
    config: dict,
    page_texts: dict[int, str],
) -> list[dict]:

    section = config[
        "classification_rules"
    ]

    pages = [
        int(page)
        for page
        in section[
            "pages"
        ]
    ]

    text = join_pages(
        page_texts,
        pages,
    )

    matches = list(
        RULE_HEADER_RE.finditer(
            text
        )
    )

    if not matches:
        raise ValueError(
            "No MDR Annex VIII rules "
            "were found."
        )

    provisions = []

    seen_rules = set()

    for index, match in enumerate(
        matches
    ):

        rule_number = int(
            match.group(1)
        )

        if rule_number in seen_rules:
            continue

        if (
            index + 1
            < len(matches)
        ):
            end = matches[
                index + 1
            ].start()

        else:
            end = len(
                text
            )

        rule_text = text[
            match.start():
            end
        ].strip()

        provisions.append(
            build_provision(
                config,
                provision_id=(
                    "MDR_ANNEX_VIII_"
                    f"RULE_{rule_number}"
                ),
                provision_type=(
                    "classification_rule"
                ),
                provision_code=str(
                    rule_number
                ),
                title=(
                    f"Règle "
                    f"{rule_number}"
                ),
                text=rule_text,
                source_section=(
                    section.get(
                        "source_section",
                        "Annexe VIII",
                    )
                ),
                source_page=(
                    find_rule_page(
                        page_texts,
                        rule_number,
                    )
                ),
            )
        )

        seen_rules.add(
            rule_number
        )

    return provisions


# ---------------------------------------------------------------------
# Annex VIII context before Rule 1
# ---------------------------------------------------------------------


def extract_classification_context(
    config: dict,
    page_texts: dict[int, str],
) -> list[dict]:
    """
    Preserve the Annex VIII definitions and application
    rules appearing before the first classification rule.

    This includes structural material such as Chapters I
    and II without interpreting it.
    """

    section = config[
        "classification_rules"
    ]

    pages = [
        int(page)
        for page
        in section[
            "pages"
        ]
    ]

    text = join_pages(
        page_texts,
        pages,
    )

    first_rule = RULE_HEADER_RE.search(
        text
    )

    if first_rule is None:
        return []

    context = text[
        :first_rule.start()
    ].strip()

    if not context:
        return []

    return [
        build_provision(
            config,
            provision_id=(
                "MDR_ANNEX_VIII_CONTEXT"
            ),
            provision_type=(
                "classification_context"
            ),
            provision_code=(
                "ANNEX_VIII"
            ),
            title=(
                "Annexe VIII — "
                "Définitions et règles "
                "d'application"
            ),
            text=context,
            source_section=(
                section.get(
                    "source_section",
                    "Annexe VIII",
                )
            ),
            source_page=(
                pages[
                    0
                ]
            ),
        )
    ]


# ---------------------------------------------------------------------
# Configured Annex excerpts
# ---------------------------------------------------------------------


def extract_annex_page_records(
    config: dict,
    page_texts: dict[int, str],
    *,
    config_key: str,
    id_prefix: str,
    title: str,
) -> list[dict]:
    """
    Store explicitly configured Annex pages as source
    excerpts.

    The cleaner does not attempt to infer requirements
    from them.
    """

    section = config[
        config_key
    ]

    source_section = section.get(
        "source_section",
        config_key,
    )

    records = []

    for page_number in section.get(
        "pages",
        [],
    ):

        page_number = int(
            page_number
        )

        records.append(
            build_provision(
                config,
                provision_id=(
                    f"{id_prefix}_"
                    f"PAGE_{page_number}"
                ),
                provision_type=(
                    "annex_excerpt"
                ),
                provision_code=(
                    source_section
                ),
                title=title,
                text=(
                    page_texts[
                        page_number
                    ]
                ),
                source_section=(
                    source_section
                ),
                source_page=(
                    page_number
                ),
            )
        )

    return records


# ---------------------------------------------------------------------
# Main cleaner
# ---------------------------------------------------------------------


def clean_regulation(
    regulation_key: str = "medical_mdr",
    *,
    force: bool = False,
) -> Path:

    config = (
        get_medical_regulation_config(
            regulation_key
        )
    )

    input_dir = Path(
        config[
            "raw_dir"
        ]
    )

    output_dir = Path(
        config[
            "clean_dir"
        ]
    )

    output_path = (
        output_dir
        / "provisions.json"
    )

    if (
        not force
        and restore_cached_file(
            output_path
        )
    ):
        print(
            f"Using cached cleaned "
            f"medical data: "
            f"{output_path}"
        )

        return output_path

    page_numbers = (
        get_all_configured_pages(
            config
        )
    )

    page_texts = load_pages(
        input_dir=input_dir,
        page_numbers=page_numbers,
    )

    provisions = []

    # Article 2 definitions found in the selected
    # definition pages.
    provisions.extend(
        extract_definitions(
            config,
            page_texts,
        )
    )

    # Articles are selected only by the external
    # configuration manifest.
    provisions.extend(
        extract_configured_articles(
            config,
            page_texts,
        )
    )

    # Preserve Annex VIII context before Rule 1.
    provisions.extend(
        extract_classification_context(
            config,
            page_texts,
        )
    )

    # Discover Annex VIII rules from their structural
    # headings rather than hard-coding rule numbers.
    provisions.extend(
        extract_classification_rules(
            config,
            page_texts,
        )
    )

    # Store the selected Annex II source excerpt.
    provisions.extend(
        extract_annex_page_records(
            config,
            page_texts,
            config_key=(
                "technical_documentation"
            ),
            id_prefix=(
                "MDR_ANNEX_II"
            ),
            title=(
                "Annexe II — "
                "Documentation technique"
            ),
        )
    )

    # Store the selected Annex IV source excerpt.
    provisions.extend(
        extract_annex_page_records(
            config,
            page_texts,
            config_key=(
                "declaration_of_conformity"
            ),
            id_prefix=(
                "MDR_ANNEX_IV"
            ),
            title=(
                "Annexe IV — "
                "Déclaration de conformité UE"
            ),
        )
    )

    # --------------------------------------------------------
    # Integrity checks
    # --------------------------------------------------------

    provision_ids = [
        provision[
            "provision_id"
        ]
        for provision
        in provisions
    ]

    if (
        len(provision_ids)
        != len(
            set(
                provision_ids
            )
        )
    ):
        raise ValueError(
            "Duplicate medical provision IDs "
            "were generated."
        )

    output = {
        "document_code":
            config[
                "document_code"
            ],

        "document_name":
            config[
                "document_name"
            ],

        "provisions":
            provisions,
    }

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    persist_file(
        output_path
    )

    print(
        f"Cleaned "
        f"{len(provisions)} "
        f"medical provisions."
    )

    print(
        f"Saved: "
        f"{output_path}"
    )

    return output_path


def main():

    parser = argparse.ArgumentParser(
        description=(
            "Clean extracted medical "
            "regulatory text."
        )
    )

    parser.add_argument(
        "--regulation",
        default="medical_mdr",
    )

    parser.add_argument(
        "--force",
        action="store_true",
    )

    args = parser.parse_args()

    clean_regulation(
        regulation_key=(
            args.regulation
        ),
        force=args.force,
    )


if __name__ == "__main__":
    main()
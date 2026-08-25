from pathlib import Path
import re

import pandas as pd


def normalize_nc_code(value):
    """
    Normalize an NC code while preserving hierarchy codes.
    """

    if pd.isna(value):
        return None

    value = str(value).strip()

    if not value:
        return None

    value = value.replace(" ", "")

    if not value.isdigit():
        return None

    return value


def parse_duty_rate(value):
    """
    Convert a simple customs-duty value to a numeric percentage.

    Complex tariff expressions are deliberately returned as None.
    """

    if pd.isna(value):
        return None

    value = str(value).strip()

    if not value:
        return None

    if value.lower() == "exemption":
        return 0.0

    normalized = value.replace(",", ".").strip()

    match = re.fullmatch(
        r"([0-9]+(?:\.[0-9]+)?)"
        r"\s*%?"
        r"(?:\s*\([^)]*\))?",
        normalized,
    )

    if not match:
        return None

    return float(match.group(1))


def is_residual_text(value):
    """
    Detect residual NC branch wording.
    """

    if value is None:
        return False

    normalized = str(value).strip().lower()

    if not normalized:
        return False

    normalized = re.sub(
        r"\s+",
        " ",
        normalized,
    )

    normalized = normalized.strip(
        "—-:;,. "
    )

    return (
        normalized == "autre"
        or normalized == "autres"
        or normalized.startswith("autre ")
        or normalized.startswith("autres ")
        or normalized == "other"
        or normalized == "others"
        or normalized.startswith("other ")
        or normalized.startswith("others ")
    )


def residual_flag(value):
    """
    Return:
        None  -> hierarchy level not present
        True  -> hierarchy level is residual
        False -> hierarchy level exists and is not residual
    """

    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    return is_residual_text(value)


def clean_pages(
    page_numbers: list[int],
    input_dir: Path,
    output_dir: Path,
    source_document: str,
) -> list[Path]:

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_files = []

    # --------------------------------------------------
    # Hierarchy state
    # --------------------------------------------------

    heading_4_code = None
    heading_4_description = None

    intermediate_heading = None
    intermediate_prefix = None
    intermediate_is_residual = None

    heading_6_code = None
    heading_6_description = None
    heading_6_is_residual = None

    subheading = None
    subheading_prefix = None
    subheading_is_residual = None

    previous_final_code = None
    previous_page_number = None

    # --------------------------------------------------
    # Process pages in numerical order
    # --------------------------------------------------

    for page_number in sorted(page_numbers):

        # --------------------------------------------------
        # Reset hierarchy when pages are not consecutive
        # --------------------------------------------------

        if (
            previous_page_number is not None
            and page_number != previous_page_number + 1
        ):
            heading_4_code = None
            heading_4_description = None

            intermediate_heading = None
            intermediate_prefix = None
            intermediate_is_residual = None

            heading_6_code = None
            heading_6_description = None
            heading_6_is_residual = None

            subheading = None
            subheading_prefix = None
            subheading_is_residual = None

            previous_final_code = None

        input_path = (
            input_dir
            / f"page-{page_number}.csv"
        )

        output_path = (
            output_dir
            / f"page-{page_number}.csv"
        )

        df = pd.read_csv(
            input_path,
            dtype=str,
            keep_default_na=False,
        )

        if len(df.columns) != 4:
            raise ValueError(
                f"Expected 4 columns on page {page_number}, "
                f"got {len(df.columns)}: "
                f"{list(df.columns)}"
            )

        df.columns = [
            "nc_code",
            "description",
            "duty_text",
            "supplementary_unit",
        ]

        # --------------------------------------------------
        # 1. Remove Textract numbered header row
        # --------------------------------------------------

        df = df[
            df["nc_code"].str.strip() != "1"
        ].copy()

        # --------------------------------------------------
        # 2. Clean raw text
        # --------------------------------------------------

        df["description"] = (
            df["description"]
            .fillna("")
            .str.strip()
        )

        df["duty_text"] = (
            df["duty_text"]
            .fillna("")
            .str.strip()
        )

        df["supplementary_unit"] = (
            df["supplementary_unit"]
            .fillna("")
            .str.strip()
        )

        df["nc_code"] = (
            df["nc_code"]
            .apply(normalize_nc_code)
        )

        # --------------------------------------------------
        # 3. Reconstruct hierarchy
        # --------------------------------------------------

        cleaned_rows = []

        for _, row in df.iterrows():

            code = row["nc_code"]
            raw_description = row["description"]

            # ----------------------------------------------
            # Blank-code hierarchy row
            # ----------------------------------------------

            if code is None or pd.isna(code):

                if not raw_description:
                    continue

                # Blank row following a final code belonging
                # to the active HS6 branch is treated as a
                # deeper subheading.
                if (
                    heading_6_code
                    and previous_final_code
                    and previous_final_code.startswith(
                        heading_6_code
                    )
                ):
                    subheading = raw_description
                    subheading_prefix = None

                    subheading_is_residual = (
                        is_residual_text(
                            raw_description
                        )
                    )

                else:
                    # Otherwise it is an intermediate
                    # hierarchy level below HS4.
                    intermediate_heading = (
                        raw_description
                    )
                    intermediate_prefix = None

                    intermediate_is_residual = (
                        is_residual_text(
                            raw_description
                        )
                    )

                    heading_6_code = None
                    heading_6_description = None
                    heading_6_is_residual = None

                    subheading = None
                    subheading_prefix = None
                    subheading_is_residual = None

                continue

            code = str(code)

            # ----------------------------------------------
            # Four-digit heading
            # ----------------------------------------------

            if len(code) == 4:

                heading_4_code = code
                heading_4_description = (
                    raw_description
                )

                intermediate_heading = None
                intermediate_prefix = None
                intermediate_is_residual = None

                heading_6_code = None
                heading_6_description = None
                heading_6_is_residual = None

                subheading = None
                subheading_prefix = None
                subheading_is_residual = None

                previous_final_code = None

                continue

            # ----------------------------------------------
            # Six-digit heading
            # ----------------------------------------------

            if len(code) == 6:

                # Prevent inheritance from another HS4
                # tariff family.
                if (
                    heading_4_code
                    and not code.startswith(
                        heading_4_code
                    )
                ):
                    heading_4_code = None
                    heading_4_description = None

                    intermediate_heading = None
                    intermediate_prefix = None
                    intermediate_is_residual = None

                # Validate intermediate hierarchy.
                if intermediate_heading:

                    candidate_prefix = code[:5]

                    if intermediate_prefix is None:
                        intermediate_prefix = (
                            candidate_prefix
                        )

                    elif not code.startswith(
                        intermediate_prefix
                    ):
                        intermediate_heading = None
                        intermediate_prefix = None
                        intermediate_is_residual = None

                heading_6_code = code
                heading_6_description = (
                    raw_description
                )

                heading_6_is_residual = (
                    is_residual_text(
                        raw_description
                    )
                )

                subheading = None
                subheading_prefix = None
                subheading_is_residual = None

                continue

            # ----------------------------------------------
            # Ignore unexpected hierarchy lengths
            # ----------------------------------------------

            if len(code) != 8:
                continue

            # ----------------------------------------------
            # Skip orphan final rows
            # ----------------------------------------------

            if heading_4_code is None:
                continue

            # ----------------------------------------------
            # Validate HS4 hierarchy
            # ----------------------------------------------

            if (
                heading_4_code
                and not code.startswith(
                    heading_4_code
                )
            ):
                heading_4_code = None
                heading_4_description = None

                intermediate_heading = None
                intermediate_prefix = None
                intermediate_is_residual = None

                heading_6_code = None
                heading_6_description = None
                heading_6_is_residual = None

                subheading = None
                subheading_prefix = None
                subheading_is_residual = None

                # Cannot safely classify this final row
                # without its HS4 hierarchy.
                continue

            # ----------------------------------------------
            # Validate intermediate heading
            # ----------------------------------------------

            if intermediate_heading:

                if intermediate_prefix is None:
                    intermediate_prefix = code[:5]

                elif not code.startswith(
                    intermediate_prefix
                ):
                    intermediate_heading = None
                    intermediate_prefix = None
                    intermediate_is_residual = None

            # ----------------------------------------------
            # Validate six-digit parent
            # ----------------------------------------------

            if heading_6_code:

                if not code.startswith(
                    heading_6_code
                ):
                    heading_6_code = None
                    heading_6_description = None
                    heading_6_is_residual = None

                    subheading = None
                    subheading_prefix = None
                    subheading_is_residual = None

            # ----------------------------------------------
            # Validate deeper blank-code branch
            # ----------------------------------------------

            if subheading:

                if subheading_prefix is None:
                    subheading_prefix = code[:7]

                elif not code.startswith(
                    subheading_prefix
                ):
                    subheading = None
                    subheading_prefix = None
                    subheading_is_residual = None

            # ----------------------------------------------
            # Effective hierarchy codes
            # ----------------------------------------------

            effective_heading_6_code = (
                heading_6_code
                if heading_6_code
                else code[:6]
            )

            effective_heading_4_code = (
                heading_4_code
                if heading_4_code
                else code[:4]
            )

            # ----------------------------------------------
            # Build complete description for embeddings
            # ----------------------------------------------

            description_parts = []

            if heading_4_description:
                description_parts.append(
                    heading_4_description
                )

            if intermediate_heading:
                description_parts.append(
                    intermediate_heading
                )

            if heading_6_description:
                description_parts.append(
                    heading_6_description
                )

            if subheading:
                description_parts.append(
                    subheading
                )

            if raw_description:
                description_parts.append(
                    raw_description
                )

            full_description = " — ".join(
                description_parts
            )

            # ----------------------------------------------
            # Residual metadata
            # ----------------------------------------------

            leaf_is_residual = (
                is_residual_text(
                    raw_description
                )
            )

            has_residual_ancestor = any(
                flag is True
                for flag in [
                    intermediate_is_residual,
                    heading_6_is_residual,
                    subheading_is_residual,
                ]
            )

            # ----------------------------------------------
            # Store final NC row
            # ----------------------------------------------

            cleaned_rows.append(
                {
                    "nc_code": code,

                    # Used for embeddings / retrieval
                    "description": full_description,

                    # HS4 hierarchy
                    "heading_4_code": (
                        effective_heading_4_code
                    ),
                    "heading_4_description": (
                        heading_4_description
                    ),

                    # Intermediate hierarchy
                    "intermediate_heading": (
                        intermediate_heading
                    ),
                    "intermediate_is_residual": (
                        intermediate_is_residual
                    ),

                    # HS6 hierarchy
                    "heading_6_code": (
                        effective_heading_6_code
                    ),
                    "heading_6_description": (
                        heading_6_description
                    ),
                    "heading_6_is_residual": (
                        heading_6_is_residual
                    ),

                    # Lower hierarchy
                    "subheading": subheading,
                    "subheading_is_residual": (
                        subheading_is_residual
                    ),

                    "leaf_description": (
                        raw_description
                    ),
                    "leaf_is_residual": (
                        leaf_is_residual
                    ),

                    # Parent metadata
                    "parent_code": (
                        effective_heading_6_code
                    ),

                    # True if any known parent level
                    # is a residual branch.
                    "has_residual_ancestor": (
                        has_residual_ancestor
                    ),

                    # Tariff
                    "duty_text": (
                        row["duty_text"]
                    ),
                    "supplementary_unit": (
                        row["supplementary_unit"]
                    ),
                }
            )

            previous_final_code = code

        # --------------------------------------------------
        # 4. Final NC rows only
        # --------------------------------------------------

        df = pd.DataFrame(
            cleaned_rows,
            columns=[
                "nc_code",
                "description",

                "heading_4_code",
                "heading_4_description",

                "intermediate_heading",
                "intermediate_is_residual",

                "heading_6_code",
                "heading_6_description",
                "heading_6_is_residual",

                "subheading",
                "subheading_is_residual",

                "leaf_description",
                "leaf_is_residual",

                "parent_code",
                "has_residual_ancestor",

                "duty_text",
                "supplementary_unit",
            ],
        )

        # --------------------------------------------------
        # 5. Parse numeric duty
        # --------------------------------------------------

        df["duty_rate"] = (
            df["duty_text"]
            .apply(parse_duty_rate)
        )

        # --------------------------------------------------
        # 6. Normalize empty text values
        # --------------------------------------------------

        text_columns = [
            "heading_4_description",
            "intermediate_heading",
            "heading_6_description",
            "subheading",
            "leaf_description",
            "supplementary_unit",
            "duty_text",
        ]

        for column in text_columns:
            df[column] = (
                df[column]
                .replace("", None)
            )

        # --------------------------------------------------
        # 7. Source metadata
        # --------------------------------------------------

        df["source_document"] = (
            source_document
        )

        df["source_section"] = None

        df["source_page"] = (
            page_number
        )

        df["source_excerpt"] = (
            df["description"]
        )

        # --------------------------------------------------
        # 8. Database-friendly order
        # --------------------------------------------------

        df = df[
            [
                "nc_code",
                "description",

                "heading_4_code",
                "heading_4_description",

                "intermediate_heading",
                "intermediate_is_residual",

                "heading_6_code",
                "heading_6_description",
                "heading_6_is_residual",

                "subheading",
                "subheading_is_residual",

                "leaf_description",
                "leaf_is_residual",

                "parent_code",
                "has_residual_ancestor",

                "duty_rate",
                "duty_text",
                "supplementary_unit",

                "source_document",
                "source_section",
                "source_page",
                "source_excerpt",
            ]
        ]

        # --------------------------------------------------
        # 9. Save
        # --------------------------------------------------

        df.to_csv(
            output_path,
            index=False,
        )

        output_files.append(
            output_path
        )

        print(
            f"Page {page_number}: "
            f"cleaned {len(df)} rows"
        )

        print(
            f"Saved: {output_path}"
        )

        print("\nPreview:")

        preview_columns = [
            "nc_code",
            "heading_4_code",
            "heading_6_code",
            "intermediate_is_residual",
            "heading_6_is_residual",
            "subheading_is_residual",
            "leaf_is_residual",
            "has_residual_ancestor",
            "leaf_description",
            "duty_rate",
        ]

        print(
            df[
                preview_columns
            ].head(20)
        )

        previous_page_number = (
            page_number
        )

    return output_files
def get_common_heading(candidates):
    """
    Return the common 4-digit NC heading if all candidates
    belong to the same heading.

    Example:
        85441110
        85446010
        85444991

    -> 8544
    """

    if not candidates:
        return None

    headings = {
        row[0][:4]
        for row in candidates
    }

    if len(headings) == 1:
        return headings.pop()

    return None


def get_common_duty_rate(candidates):
    """
    Return a common duty rate if all retrieved candidates
    have the same standard NC duty rate.

    If the rates differ, return None.
    """

    if not candidates:
        return None

    rates = {
        float(row[2])
        for row in candidates
        if row[2] is not None
    }

    if len(rates) == 1:
        return rates.pop()

    return None


def get_selected_candidate(nc_code, candidates):
    """
    Find the full candidate row corresponding to the
    NC code selected by the LLM.
    """

    for candidate in candidates:
        if candidate[0] == nc_code:
            return candidate

    return None


def resolve_classification(classification, candidates):
    """
    Resolve the strongest classification level that can
    safely be established.

    Possible resolutions:

    - 8_digit:
      The LLM selected a specific NC code.

    - 4_digit_heading:
      The exact NC code is uncertain, but all retrieved
      candidates belong to the same 4-digit heading.

    - unresolved:
      Even the 4-digit heading cannot be established safely.
    """

    # --------------------------------------------------
    # Exact 8-digit classification
    # --------------------------------------------------

    if classification["status"] == "selected":

        nc_code = classification["nc_code"]

        selected = get_selected_candidate(
            nc_code,
            candidates,
        )

        if selected is None:
            raise ValueError(
                "Selected NC code was not found "
                "in retrieved candidates."
            )

        return {
            **classification,
            "resolution": "8_digit",
            "heading_code": nc_code[:4],
            "description": selected[1],
            "standard_duty_rate": (
                float(selected[2])
                if selected[2] is not None
                else None
            ),
        }

    # --------------------------------------------------
    # Exact classification uncertain
    # --------------------------------------------------

    heading_code = get_common_heading(
        candidates
    )

    standard_rate = get_common_duty_rate(
        candidates
    )

    # We can safely establish the 4-digit heading.
    if heading_code is not None:
        return {
            **classification,
            "resolution": "4_digit_heading",
            "heading_code": heading_code,
            "standard_duty_rate": standard_rate,
        }

    # --------------------------------------------------
    # No reliable classification level
    # --------------------------------------------------

    return {
        **classification,
        "resolution": "unresolved",
        "heading_code": None,
        "standard_duty_rate": None,
    }
def get_common_heading(candidates):
    if not candidates:
        return None

    headings = {
        str(row[0])[:4]
        for row in candidates
    }

    if len(headings) == 1:
        return headings.pop()

    return None


def get_common_duty_rate(candidates):
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


def get_selected_candidate(
    nc_code,
    candidates,
):
    for candidate in candidates:
        if str(candidate[0]) == str(nc_code):
            return candidate

    return None


def resolve_classification(
    classification,
    candidates,
):
    """
    Resolve the strongest classification level
    that can safely be established.

    Possible resolutions:

    - 8_digit
    - 4_digit_heading
    - unresolved
    """

    # Exact NC8 classification
    if (
        classification["status"] == "SUPPORTED"
        and classification.get("nc_code")
    ):
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

    # Exact NC8 is uncertain
    if (
        classification["status"]
        == "UNCERTAIN_CLASSIFICATION"
    ):
        heading_code = get_common_heading(
            candidates
        )

        standard_rate = get_common_duty_rate(
            candidates
        )

        if heading_code is not None:
            return {
                **classification,
                "resolution": "4_digit_heading",
                "heading_code": heading_code,
                "standard_duty_rate": standard_rate,
            }

    return {
        **classification,
        "resolution": "unresolved",
        "heading_code": None,
        "standard_duty_rate": None,
    }
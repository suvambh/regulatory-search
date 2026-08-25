import math

import psycopg

from models import Status, TariffResult


DB_URL = (
    "postgresql://regulatory_app:"
    "local_dev_password@localhost:5433/regulatory"
)


def get_tariff_item(
    nc_code: str,
    db_url: str = DB_URL,
):
    """
    Retrieve the authoritative tariff row by exact NC code.

    Vector search is NOT used here.
    """

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    nc_code,
                    description,
                    duty_rate,
                    duty_text,
                    supplementary_unit,
                    source_document,
                    source_section,
                    source_page,
                    source_excerpt
                FROM tariff_items
                WHERE nc_code = %s
                """,
                (nc_code,),
            )

            row = cur.fetchone()

    if row is None:
        return None

    return {
        "nc_code": row[0],
        "description": row[1],
        "duty_rate": (
            float(row[2])
            if row[2] is not None
            else None
        ),
        "duty_text": row[3],
        "supplementary_unit": row[4],
        "source_document": row[5],
        "source_section": row[6],
        "source_page": row[7],
        "source_excerpt": row[8],
    }


def calculate_standard_tariff(
    nc_code: str,
    goods_value_eur: float,
    db_url: str = DB_URL,
) -> TariffResult:

    item = get_tariff_item(
        nc_code=nc_code,
        db_url=db_url,
    )

    if item is None:
        return TariffResult(
            status=Status.MISSING_PRODUCT_INFORMATION,
            calculation_basis="NC code not found in tariff corpus.",
        )

    rate = item["duty_rate"]
    duty_text = item["duty_text"]

    # Defensive protection against PostgreSQL/Python NaN.
    if (
        rate is not None
        and isinstance(rate, float)
        and math.isnan(rate)
    ):
        rate = None

    # ----------------------------------------
    # Simple percentage tariff
    # ----------------------------------------

    if rate is not None:

        duty = (
            goods_value_eur
            * rate
            / 100
        )

        return TariffResult(
            status=Status.SUPPORTED,
            standard_rate_pct=rate,
            duty_text=duty_text,
            standard_duty_eur=round(
                duty,
                2,
            ),
            calculation_basis=(
                f"{goods_value_eur:.2f} EUR "
                f"× {rate}%"
            ),
        )

    # ----------------------------------------
    # Complex/specific tariff
    # ----------------------------------------

    return TariffResult(
        status=Status.MISSING_PRODUCT_INFORMATION,
        standard_rate_pct=None,
        duty_text=duty_text,
        standard_duty_eur=None,
        calculation_basis=(
            "The tariff is not expressed as a simple "
            "percentage of customs value."
        ),
        missing_information=[
            "Quantity or weight required by the tariff expression"
        ],
    )
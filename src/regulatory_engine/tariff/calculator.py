import math

from regulatory_engine.models import (
    Status,
    TariffResult,
)

from regulatory_engine.repositories.tariff_repository import (
    get_tariff_item,
)


def calculate_standard_tariff(
    nc_code: str,
    goods_value_eur: float,
    db_url: str | None = None,
) -> TariffResult:
    """
    Calculate the standard customs duty for an exact NC code.

    Only simple percentage-based tariffs are currently
    calculated automatically.
    """

    item = get_tariff_item(
        nc_code=nc_code,
        db_url=db_url,
    )

    if item is None:
        return TariffResult(
            status=(
                Status.MISSING_PRODUCT_INFORMATION
            ),
            calculation_basis=(
                "NC code not found in tariff corpus."
            ),
        )

    rate = item[
        "duty_rate"
    ]

    duty_text = item[
        "duty_text"
    ]

    # Defensive protection against
    # PostgreSQL/Python NaN values.
    if (
        rate is not None
        and isinstance(rate, float)
        and math.isnan(rate)
    ):
        rate = None

    # --------------------------------------------------
    # Simple percentage tariff
    # --------------------------------------------------

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

    # --------------------------------------------------
    # Complex / specific tariff
    # --------------------------------------------------

    return TariffResult(
        status=(
            Status.MISSING_PRODUCT_INFORMATION
        ),

        standard_rate_pct=None,

        duty_text=duty_text,

        standard_duty_eur=None,

        calculation_basis=(
            "The tariff is not expressed as a simple "
            "percentage of customs value."
        ),

        missing_information=[
            (
                "Quantity or weight required by "
                "the tariff expression"
            )
        ],
    )
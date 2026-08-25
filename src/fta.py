import psycopg

from fta_config import (
    load_fta_config,
)

from classify_fta_tariff import (
    classify_fta_tariff_line,
)


DB_URL = (
    "postgresql://regulatory_app:"
    "local_dev_password@localhost:5433/regulatory"
)


def normalize_country(value):
    if not value:
        return None

    return str(
        value
    ).strip().lower()


def find_applicable_agreement(
    exporter_country: str,
    importer_country: str,
):
    """
    Find the applicable agreement using the
    shared FTA configuration.

    Country names are expected in French,
    matching the scenario/config values.
    """

    exporter = normalize_country(
        exporter_country
    )

    importer = normalize_country(
        importer_country
    )

    if not exporter or not importer:
        return None

    fta_config = load_fta_config()

    for (
        agreement_key,
        config,
    ) in fta_config.items():

        configured_exporter = (
            normalize_country(
                config[
                    "exporter_country"
                ]
            )
        )

        configured_importer = (
            normalize_country(
                config[
                    "importer_country"
                ]
            )
        )

        if (
            exporter
            == configured_exporter
            and importer
            == configured_importer
        ):
            return {
                "agreement_key":
                    agreement_key,

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
            }

    return None


def find_legal_basis(
    agreement_code: str,
):
    """
    Retrieve all intentionally ingested legal
    provisions for the applicable agreement.

    Article numbers are not hardcoded here.
    """

    with psycopg.connect(
        DB_URL
    ) as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    article,
                    section,
                    text,
                    source_document,
                    source_page,
                    source_excerpt
                FROM fta_chunks
                WHERE agreement_code = %s
                  AND chunk_type = 'agreement_article'
                ORDER BY
                    source_page,
                    article;
                """,
                (
                    agreement_code,
                ),
            )

            rows = cur.fetchall()

    return [
        {
            "article":
                row[0],

            "section":
                row[1],

            "text":
                row[2],

            "source_document":
                row[3],

            "source_page":
                row[4],

            "source_excerpt":
                row[5],
        }
        for row in rows
    ]


def find_origin_rule(
    agreement_code: str,
    nc_code: str,
):
    """
    Find the product-specific origin rule.

    Current tariff classification uses
    8-digit NC codes.

    The origin-rule tables loaded for this
    prototype are indexed at HS4 level.

    Examples:
        85441110 -> 8544
        85285291 -> 8528
    """

    if not nc_code:
        return None

    nc_code = str(
        nc_code
    ).strip()

    if len(nc_code) < 4:
        return None

    hs_code = nc_code[
        :4
    ]

    with psycopg.connect(
        DB_URL
    ) as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    hs_code,
                    description,
                    rule_text,
                    max_non_originating_material_pct,
                    value_basis,
                    source_document,
                    source_section,
                    source_page,
                    source_excerpt
                FROM fta_origin_rules
                WHERE agreement_code = %s
                  AND hs_code = %s
                LIMIT 1;
                """,
                (
                    agreement_code,
                    hs_code,
                ),
            )

            row = cur.fetchone()

    if row is None:
        return None

    return {
        "hs_code":
            row[0],

        "description":
            row[1],

        "rule_text":
            row[2],

        "max_non_originating_material_pct": (
            float(
                row[3]
            )
            if row[3] is not None
            else None
        ),

        "value_basis":
            row[4],

        "source_document":
            row[5],

        "source_section":
            row[6],

        "source_page":
            row[7],

        "source_excerpt":
            row[8],
    }


def find_tariff_schedule_line(
    agreement_key: str,
    agreement_code: str,
    nc_code: str,
    product_description: str | None,
    current_nc_description: str | None,
):
    """
    Reconcile the current NC classification with
    the historical tariff nomenclature used by
    the FTA schedule.

    Only agreements containing a tariff_schedule
    configuration use this step.

    This does NOT determine tariff-dismantling
    mechanics or independently determine a
    current preferential rate.
    """

    fta_config = load_fta_config()

    agreement_config = fta_config[
        agreement_key
    ]

    # Not every agreement requires a historical
    # tariff-schedule reconciliation step.
    if (
        "tariff_schedule"
        not in agreement_config
    ):
        return None

    # Historical semantic reconciliation requires
    # the actual product description.
    if not product_description:
        return {
            "status":
                "NOT_EVALUATED",

            "reason": (
                "La description du produit "
                "est nécessaire pour rapprocher "
                "la nomenclature NC actuelle "
                "de la nomenclature historique "
                "de l'accord."
            ),
        }

    result = classify_fta_tariff_line(
        agreement_code=(
            agreement_code
        ),
        nc_code=(
            nc_code
        ),
        product_description=(
            product_description
        ),
        current_nc_description=(
            current_nc_description
        ),
        limit=5,
    )

    status = result[
        "status"
    ]

    if status != "SUPPORTED":
        return {
            "status":
                status,

            "reason":
                result.get(
                    "reason"
                ),
        }

    candidate = result[
        "candidate"
    ]

    return {
        "status":
            "SUPPORTED",

        "tariff_code":
            candidate[
                "tariff_code"
            ],

        "description":
            candidate[
                "description"
            ],

        "base_rate_pct":
            candidate[
                "base_rate_pct"
            ],

        "base_rate_text":
            candidate[
                "base_rate_text"
            ],

        "tariff_category":
            candidate[
                "tariff_category"
            ],

        "similarity":
            candidate[
                "similarity"
            ],

        "reason":
            result.get(
                "reason"
            ),

        "source_page":
            candidate[
                "source_page"
            ],

        "source_excerpt":
            candidate[
                "source_excerpt"
            ],
    }


def get_preferential_context(
    nc_code: str,
    exporter_country: str,
    importer_country: str,
    product_description: str | None = None,
    current_nc_description: str | None = None,
):
    """
    Build the complete FTA context for a
    classified product.

    Runtime flow:

        exporter / importer
                ↓
        applicable agreement
                ↓
        legal provisions
                ↓
        HS4 origin rule
                ↓
        historical tariff reconciliation
        when required by the agreement

    Preferential origin is NOT independently
    proven by this function.
    """

    agreement = (
        find_applicable_agreement(
            exporter_country=(
                exporter_country
            ),
            importer_country=(
                importer_country
            ),
        )
    )

    if agreement is None:
        return None

    agreement_key = agreement[
        "agreement_key"
    ]

    agreement_code = agreement[
        "agreement_code"
    ]

    legal_basis = find_legal_basis(
        agreement_code=(
            agreement_code
        ),
    )

    origin_rule = find_origin_rule(
        agreement_code=(
            agreement_code
        ),
        nc_code=(
            nc_code
        ),
    )

    tariff_schedule = (
        find_tariff_schedule_line(
            agreement_key=(
                agreement_key
            ),
            agreement_code=(
                agreement_code
            ),
            nc_code=(
                nc_code
            ),
            product_description=(
                product_description
            ),
            current_nc_description=(
                current_nc_description
            ),
        )
    )

    # agreement_key is useful internally for
    # config lookup, but is not part of the
    # external agreement result.
    public_agreement = {
        key: value
        for key, value
        in agreement.items()
        if key != "agreement_key"
    }

    return {
        "agreement":
            public_agreement,

        "legal_basis":
            legal_basis,

        "origin_rule":
            origin_rule,

        "origin_verification": {
            "status":
                "NOT_VERIFIED",

            "reason": (
                "Le scénario indique le pays "
                "d'exportation, mais ne fournit "
                "pas les informations de "
                "fabrication et de valeur des "
                "matières nécessaires pour "
                "vérifier indépendamment la "
                "règle d'origine préférentielle."
            ),
        },

        "tariff_schedule":
            tariff_schedule,
    }


if __name__ == "__main__":

    from pprint import pprint

    print(
        "\n--- MAROC ---"
    )

    morocco_result = (
        get_preferential_context(
            nc_code="85441110",
            exporter_country="Maroc",
            importer_country="France",
            product_description=(
                "Câble électrique en cuivre"
            ),
            current_nc_description=(
                "Fils pour bobinages en cuivre"
            ),
        )
    )

    pprint(
        morocco_result,
        sort_dicts=False,
    )

    print(
        "\n--- COREE DU SUD ---"
    )

    korea_result = (
        get_preferential_context(
            nc_code="85285291",
            exporter_country=(
                "Corée du Sud"
            ),
            importer_country=(
                "France"
            ),

            product_description=(
                "Moniteur LCD couleur conçu "
                "pour être connecté directement "
                "à une machine automatique de "
                "traitement de l'information"
            ),

            current_nc_description=(
                "Moniteurs capables d'être "
                "connectés directement à une "
                "machine automatique de traitement "
                "de l'information du no 8471 "
                "et conçus pour être utilisés "
                "avec celle-ci"
            ),
        )
    )

    pprint(
        korea_result,
        sort_dicts=False,
    )
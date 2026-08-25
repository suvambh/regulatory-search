from preference import evaluate_tariff_preference


result = evaluate_tariff_preference(
    nc_code="85446010",
    classification_status="selected",
    standard_rate=3.7,
    value_eur=10000,
    exporter="Maroc",
    importer="France",
    product_scope="industrial",
    preferential_origin_confirmed=True,
)

print(result)
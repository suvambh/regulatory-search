import json

from preference import evaluate_tariff_preference
from search import search_and_classify
from regulatory_engine.classification.resolution import (
    resolve_classification,
)

def main():
    request = {
        "produit": "Câbles électriques en cuivre isolés",
        "pays_exportateur": "Maroc",
        "pays_importateur": "France",
        "valeur_marchandise_eur": 10000,
    }

    # 1. Search + LLM classification
    search_result = search_and_classify(
        request["produit"]
    )

    candidates = search_result["candidates"]
    raw_classification = search_result["classification"]

    print("\n--- VECTOR SEARCH ---\n")
    for candidate in candidates:
        print(candidate)

    print("\n--- RAW CLASSIFICATION ---\n")
    print(
        json.dumps(
            raw_classification,
            indent=2,
            ensure_ascii=False,
        )
    )

    # 2. Resolve strongest reliable classification level
    classification = resolve_classification(
        raw_classification,
        candidates,
    )

    print("\n--- RESOLVED CLASSIFICATION ---\n")
    print(
        json.dumps(
            classification,
            indent=2,
            ensure_ascii=False,
        )
    )

    # 3. Evaluate Morocco preference
    preference = evaluate_tariff_preference(
        classification=classification,
        value_eur=request["valeur_marchandise_eur"],
        exporter=request["pays_exportateur"],
        importer=request["pays_importateur"],

        # Temporary Phase A assumption.
        preferential_origin_confirmed=True,
    )

    print("\n--- PREFERENCE ---\n")
    print(
        json.dumps(
            preference,
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
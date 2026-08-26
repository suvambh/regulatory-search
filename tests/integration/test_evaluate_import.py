from regulatory_engine.application import (
    evaluate_import,
)
from regulatory_engine.models import (
    ImportRequest,
)


request = ImportRequest(
    produit="Écran LCD moniteur 27 pouces",
    pays_exportateur="Corée du Sud",
    pays_importateur="France",
    valeur_marchandise_eur=300,
)

result = evaluate_import(
    request
)

print(
    result
)
from dataclasses import dataclass


@dataclass(frozen=True)
class ImportRequest:
    produit: str
    pays_exportateur: str
    pays_importateur: str
    valeur_marchandise_eur: float
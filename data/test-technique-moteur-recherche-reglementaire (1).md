# Test Technique — Moteur de Recherche Réglementaire

## Contexte

Notre plateforme aide des acheteurs internationaux (sourcing B2B) à maîtriser les coûts liés à l'importation de marchandises. Lorsqu'un acheteur reçoit un devis de son fournisseur, il veut avoir une vision claire de ce que la marchandise va lui coûter « à la porte », au-delà du prix fournisseur.

Aujourd'hui, ces informations sont dispersées dans de nombreuses sources officielles et l'acheteur perd un temps considérable à les chercher manuellement.

On veut automatiser cette recherche.

Le cas d'usage typique : un acheteur importe **plusieurs articles différents** dans une même commande (par exemple 3 types de composants électroniques + 1 équipement médical). Il veut une vision consolidée du surcoût réglementaire pour l'ensemble de sa commande.

---

## Objectif

Construire un **système** déployé dans le cloud qui, à partir d'une description de produit et d'un contexte d'import (origine, destination), retourne les informations réglementaires utiles à l'acheteur pour évaluer son coût total.

Le système doit :

1. Exploiter le corpus de documents fourni ci-dessous
2. Répondre aux questions de l'acheteur de manière fiable et sourcée
3. Permettre à l'acheteur d'interagir avec le système (le format d'interaction est à votre appréciation)

---

## Corpus de documents

Tous les documents sont téléchargeables gratuitement depuis EUR-Lex. Le candidat doit constituer sa base à partir des sources suivantes :

| # | Document | URL de téléchargement (PDF) | Contenu clé |
| --- | --- | --- | --- |
| 1 | **Nomenclature Combinée 2024** (Règlement d'exécution 2024/339 — Annexe I) | [EUR-Lex 32024R0339](https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:32024R0339) | Tableau des taux de droits par code NC — couvre TOUS les chapitres (84, 85, 90, etc.) |
| 2 | **Accord d'association UE-Maroc** (JO L 70/2000 — texte intégral) | [EUR-Lex JO L:2000:070](https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=OJ:L:2000:070:FULL) | Préférences tarifaires, protocoles d'origine, listes de produits couverts |
| 3 | **Règlement (CE) 765/2008** — Accréditation et marquage CE | [EUR-Lex 32008R0765](https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:32008R0765) | Obligations marquage CE, organismes notifiés, surveillance du marché |
| 4 | **Règlement (UE) 2017/745** — Dispositifs médicaux (MDR) | [EUR-Lex 32017R0745](https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:32017R0745) | Classification des dispositifs médicaux, évaluation de conformité, organismes notifiés |
| 5 | **Code des douanes de l'Union (CDU)** — Règlement 952/2013 | [EUR-Lex 32013R0952](https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:32013R0952) | Valeur en douane, règles de classement tarifaire, origine des marchandises |
| 6 | **Accord de libre-échange UE-Corée du Sud** | [EUR-Lex 22011A0514(01)](https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:22011A0514(01)) | Préférences tarifaires, calendrier de démantèlement, règles d'origine |

**Important** : Le corpus est volontairement limité et volumineux. Vous n'êtes pas obligé d'ingérer l'intégralité de chaque document — un sous-ensemble pertinent pour couvrir les scénarios de test est acceptable. On évalue votre capacité à identifier ce qui est pertinent et à justifier vos choix de périmètre.

---

## Scénarios de test

Votre système doit répondre correctement aux scénarios suivants. Pour chaque scénario, le système doit retourner :

- Les informations réglementaires pertinentes pour l'acheteur
- Une estimation chiffrée du surcoût réglementaire
- Les **sources exactes** (document, article/section, extrait)

*Note : la structure exacte de la réponse est à votre appréciation — c'est au candidat de définir ce qui est le plus utile pour l'acheteur.*

---

### Scénario 1 — Import standard

```json
{
  "produit": "Ordinateur portable 14 pouces",
  "pays_exportateur": "Chine",
  "pays_importateur": "France",
  "valeur_marchandise_eur": 500
}
```

---

### Scénario 2 — Préférence tarifaire

```json
{
  "produit": "Câbles électriques en cuivre isolés",
  "pays_exportateur": "Maroc",
  "pays_importateur": "France",
  "valeur_marchandise_eur": 10000
}
```

---

### Scénario 3 — Accord de libre-échange

```json
{
  "produit": "Écran LCD moniteur 27 pouces",
  "pays_exportateur": "Corée du Sud",
  "pays_importateur": "France",
  "valeur_marchandise_eur": 300
}
```

---

### Scénario 4 — Produit réglementé

```json
{
  "produit": "Oxymètre de pouls digital (mesure SpO2 et fréquence cardiaque)",
  "pays_exportateur": "Chine",
  "pays_importateur": "France",
  "valeur_marchandise_eur": 2000
}
```

---

### Scénario 5 — Produit spécialisé

```json
{
  "produit": "Prothèse de hanche en titane",
  "pays_exportateur": "Inde",
  "pays_importateur": "France",
  "valeur_marchandise_eur": 15000
}
```

---

### Scénario 6 — Produit alimentaire

```json
{
  "produit": "Huile d'olive vierge extra bio",
  "pays_exportateur": "Tunisie",
  "pays_importateur": "France",
  "valeur_marchandise_eur": 5000
}
```

---

### Scénario 7 — Description technique

```json
{
  "produit": "Batterie lithium-ion rechargeable haute capacité pour véhicule électrique",
  "pays_exportateur": "Chine",
  "pays_importateur": "France",
  "valeur_marchandise_eur": 8000
}
```

---

## Livrables attendus

| # | Livrable | Format |
| --- | --- | --- |
| 1 | **Schéma d'architecture** | Diagramme montrant les composants et leurs interactions |
| 2 | **Code source** | Repository Git avec README et instructions de déploiement/exécution |
| 3 | **Pipeline d'indexation** | Code qui ingère les PDF et les rend recherchables |
| 4 | **Interface utilisateur** | Une interface permettant à l'acheteur d'interroger le système et de visualiser les résultats. Le choix du format est libre (application web, chatbot, dashboard, CLI amélioré, notebook interactif…). On évalue la pertinence du choix UX par rapport au besoin de l'acheteur. |
| 5 | **Résultats des 7 scénarios** | Document ou notebook avec les inputs, outputs réels, et analyse de la qualité |
| 6 | **Note technique (2-3 pages)** | Choix techniques justifiés, compromis, limites identifiées, estimation des coûts cloud, améliorations futures. **Répondez notamment à cette question** : « Pourquoi une recherche par mots-clés seule ne suffit-elle pas pour ce cas d'usage ? Illustrez avec un exemple concret tiré de vos tests. » |

**Bonus** : Toute initiative qui améliore l'expérience de l'acheteur sera valorisée.

---

## ️ Contraintes

| Contrainte | Détail |
| --- | --- |
| **Cloud** | Déploiement obligatoire sur un cloud provider (AWS, GCP, ou Azure) |
| **Budget** | Maximum **200€** de consommation cloud. Si vous estimez que l'approche optimale dépasse ce budget, présentez deux architectures : une dans le budget et une « idéale » avec justification du surcoût. |
| **Durée** | 1 semaine (7 jours calendaires) |
| **Architecture** | Libre — aucune technologie imposée. C'est au candidat de choisir et justifier son approche |
| **Données** | Uniquement les PDF listés ci-dessus. Pas de source externe supplémentaire pour les réponses (mais des outils/APIs externes pour le traitement sont autorisés) |
| **Performance** | Le temps de réponse cible pour une requête est de **moins de 30 secondes**. Si votre système est plus lent, expliquez pourquoi dans la note technique et proposez des pistes d'optimisation. |

---

## Contact & Questions

Le candidat est encouragé à poser des questions de clarification. C'est un signal positif — on évalue aussi la capacité à identifier les ambiguïtés et à les lever de manière proactive.

- **Disponibilité** : réponse sous 24h en jours ouvrés

---

## Restitution

- **Présentation orale** : 20 minutes de démo + 10 minutes de questions
- Le candidat montre les 7 scénarios en live
- On discute des choix d'architecture, des compromis, et de ce qu'il ferait avec plus de temps/budget
- On évalue la capacité du candidat à expliquer ses choix à un interlocuteur non-technique (l'acheteur)

---

## Conseils

- Commencez par un cas simple de bout en bout avant d'élargir
- La qualité de la recherche et la précision des citations sont plus importantes que le nombre de fonctionnalités
- Documentez vos choix et compromis — on évalue votre raisonnement autant que le résultat
- Un système honnête (qui dit « je ne sais pas ») vaut mieux qu'un système qui invente
- N'hésitez pas à nous contacter si quelque chose n'est pas clair dans ce document

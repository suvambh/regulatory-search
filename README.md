# Regulatory Engine

Cloud-based prototype for EU import tariff classification and preferential trade analysis.

The system takes a product description, exporter country, importer country, and goods value, then retrieves the relevant customs classification and tariff context from a regulatory corpus.

The prototype combines deterministic regulatory logic, semantic retrieval with PostgreSQL/pgvector, and LLM-based ambiguity resolution using Amazon Bedrock.

---

## 1. Overview

A typical request contains:

```json
{
  "produit": "Ordinateur portable 14 pouces",
  "pays_exportateur": "Chine",
  "pays_importateur": "France",
  "valeur_marchandise_eur": 500
}
```

The engine attempts to determine:

* the relevant EU Combined Nomenclature (NC) classification;
* the standard customs-duty rate;
* the estimated customs duty when enough information is available;
* whether a supported Free Trade Agreement applies;
* the applicable origin rule;
* the relevant historical FTA tariff line when nomenclature versions differ;
* the preferential tariff when directly supported by the source evidence.

The system is deliberately conservative. If the supplied product description does not support an exact classification or tariff calculation, the engine returns an uncertainty status instead of inventing a result.

---

## 2. Architecture

The deployed application uses AWS:

```text
User
  │
  ▼
Application Load Balancer
  │
  ▼
Amazon ECS / Fargate
  │
  ├── Streamlit application
  └── regulatory_engine Python package
          │
          ├── Aurora PostgreSQL + pgvector
          ├── Amazon Bedrock
          ├── Amazon S3
          └── Amazon Textract
```

AWS region:

```text
eu-west-3
```

Models:

```text
Embeddings
cohere.embed-multilingual-v3

Reasoning / classification
eu.amazon.nova-pro-v1:0
```

### Component responsibilities

**Amazon ECS / Fargate** runs the packaged Python application and Streamlit interface.

**Aurora PostgreSQL + pgvector** stores structured tariff data, FTA rules, source evidence, and semantic embeddings.

**Amazon S3** stores the regulatory corpus and reusable extraction/cleaning artifacts.

**Amazon Textract** extracts structured data from relevant PDF pages.

**Amazon Bedrock** provides multilingual embeddings and LLM-based ambiguity resolution.

---

## 3. Analysis approach

The system avoids using an LLM when deterministic regulatory logic is sufficient.

The main runtime pattern is:

```text
Structured lookup / filtering
          ↓
Semantic candidate retrieval
          ↓
Deterministic validation
          ↓
LLM ambiguity resolution when required
          ↓
Tariff / FTA calculation
```

### NC classification

Product descriptions are embedded and compared against indexed NC tariff items.

The highest semantic similarity result is not automatically accepted. A small candidate set is passed to the classifier, which evaluates the description and hierarchy before selecting a tariff code.

This is important because semantic similarity alone can rank related but legally different products highly.

For example, a rechargeable lithium-ion vehicle battery may retrieve primary lithium batteries among the closest semantic results. The reasoning layer must distinguish an **accumulator** from a **primary battery** before selecting the NC code.

### Classification uncertainty

The engine does not assume that the top retrieved candidates represent every legally possible tariff branch.

For example:

```text
"Câbles électriques en cuivre isolés"
```

can be placed under HS heading `8544`, but the exact NC8 classification depends on characteristics such as voltage, connectors, and intended use.

The engine therefore does not calculate a standard tariff simply because the top semantic candidates happen to share the same rate.

Instead:

```text
Known HS4 + uncertain NC8
        ↓
standard tariff not determined
        ↓
request additional product information
```

### Historical FTA reconciliation

FTA tariff schedules may use an older nomenclature than the current EU NC.

The engine therefore does not require exact code equality.

For supported agreements:

```text
Current NC classification
        ↓
Select relevant historical HS family
        ↓
Retrieve historical tariff candidates
        ↓
Compare product meaning and hierarchy
        ↓
Resolve only when evidence is sufficient
```

This is particularly important for the EU–South Korea agreement.

---

## 4. Regulatory data

The prototype uses a deliberately limited subset of the supplied regulatory corpus covering the required evaluation scenarios.

### Main database tables

```text
tariff_items
fta_chunks
fta_origin_rules
fta_tariff_lines
```

`tariff_items` contains current NC classifications, descriptions, hierarchy information, standard tariff data, source evidence, and embeddings.

`fta_chunks` contains selected legal provisions from supported trade agreements.

`fta_origin_rules` contains product-specific origin rules indexed primarily by agreement and HS heading.

`fta_tariff_lines` contains historical FTA tariff schedules used for nomenclature reconciliation.

### Cached ingestion artifacts

Reusable intermediate data is stored in S3:

```text
processed/
├── raw/
│   ├── nc/
│   └── fta/
└── cleaned/
    ├── nc/
    └── fta/
```

This avoids repeating Textract processing unnecessarily.

Embeddings are also preserved when the underlying description has not changed.

---

## 5. Repository structure

```text
app/
└── streamlit_app.py

config/
└── fta_agreements.json

corpus/
├── nc2024.pdf
├── korea.pdf
├── maroc.pdf
└── medical.pdf

database/
└── migrations/

scripts/
├── evaluate_scenarios.py
├── inspect_fta.py
└── scan_pdf_pages.py

src/regulatory_engine/
├── application/
│   └── evaluate.py
├── classification/
├── fta/
├── infrastructure/
├── ingestion/
│   ├── nc/
│   └── fta/
├── models/
├── repositories/
└── tariff/

tests/
├── integration/
└── manual/
```

The main public application function is:

```python
evaluate_import(request: ImportRequest)
```

The Streamlit UI and evaluation scripts use the same application layer.

---

## 6. Local setup

### Prerequisites

* Python 3.12+
* Docker
* Docker Compose
* AWS CLI
* AWS credentials with access to Bedrock and Textract in `eu-west-3`

Configure AWS credentials:

```bash
aws configure
```

### Build the containers

```bash
docker compose build web
docker compose --profile ingestion build ingestion
```

### Start PostgreSQL

```bash
docker compose up -d db
```

Check its status:

```bash
docker compose ps
```

---

## 7. Build the regulatory database

Database migrations are run automatically by the ingestion pipelines.

### NC ingestion

```bash
docker compose --profile ingestion run --rm ingestion \
  python -m regulatory_engine.ingestion.nc.run
```

The NC pipeline performs:

```text
database migrations
→ extract or restore selected pages
→ reconstruct NC hierarchy
→ clean tariff records
→ load PostgreSQL
→ generate missing embeddings
```

Only the pages required for the prototype scenarios are processed.

### FTA ingestion

```bash
docker compose --profile ingestion run --rm ingestion \
  python -m regulatory_engine.ingestion.fta.run
```

The FTA pipeline performs:

```text
database migrations
→ extract tariff/origin data
→ extract legal provisions
→ clean legal text
→ clean origin rules
→ clean historical tariff schedule
→ load PostgreSQL
→ generate missing tariff embeddings
```

The prototype currently contains structured FTA support for:

```text
EU–Morocco
EU–South Korea
```

---

## 8. Run the application

Start Streamlit:

```bash
docker compose up -d web
```

Open:

```text
http://localhost:8501
```

View application logs:

```bash
docker compose logs -f web
```

A hosted AWS deployment can also be exposed through the Application Load Balancer for demonstration without requiring the evaluator to configure an AWS environment.

---

## 9. Run the evaluation scenarios

The seven supplied scenarios can be executed directly against the application layer without Streamlit:

```bash
python scripts/evaluate_scenarios.py
```

Inputs are stored in:

```text
data/evaluation/scenarios.json
```

Results are generated under:

```text
data/evaluation/results/
├── scenario_1.json
├── scenario_2.json
├── scenario_3.json
├── scenario_4.json
├── scenario_5.json
├── scenario_6.json
└── scenario_7.json
```

The scenarios cover:

1. Laptop computer
2. Electrical cables imported from Morocco
3. LCD monitor imported from South Korea
4. Pulse oximeter
5. Hip prosthesis
6. Extra virgin olive oil
7. Electric-vehicle lithium-ion battery

These scenarios are used as regression cases while improving classification and retrieval quality.

---

## 10. Example behaviours

### Exact classification

For:

```text
Ordinateur portable 14 pouces
```

the system classifies the product as:

```text
NC 84713000
Standard duty: exemption / 0%
```

### Classification uncertainty

For:

```text
Câbles électriques en cuivre isolés
```

the system can identify HS heading:

```text
8544
```

but does not calculate a standard tariff without enough information to determine the exact NC8 branch.

The Morocco agreement and its HS 8544 origin rule can still be retrieved independently.

### Specific rather than percentage tariff

For:

```text
Huile d'olive vierge extra bio
```

the tariff is expressed as:

```text
124.5 EUR / 100 kg net
```

The merchandise value alone is therefore insufficient to calculate customs duty. The engine requests shipment weight rather than attempting an incorrect percentage calculation.

---

## 11. Database verification

To inspect the number of loaded regulatory records:

```bash
docker compose exec db \
  psql -U regulatory_app -d regulatory \
  -c "
    SELECT 'tariff_items' AS table_name, COUNT(*) FROM tariff_items
    UNION ALL
    SELECT 'fta_chunks', COUNT(*) FROM fta_chunks
    UNION ALL
    SELECT 'fta_origin_rules', COUNT(*) FROM fta_origin_rules
    UNION ALL
    SELECT 'fta_tariff_lines', COUNT(*) FROM fta_tariff_lines;
  "
```

---

## 12. Rebuild from scratch

Delete the local PostgreSQL volume:

```bash
docker compose down -v
```

Start a new database:

```bash
docker compose up -d db
```

Rebuild the regulatory data:

```bash
docker compose --profile ingestion run --rm ingestion \
  python -m regulatory_engine.ingestion.nc.run

docker compose --profile ingestion run --rm ingestion \
  python -m regulatory_engine.ingestion.fta.run
```

Then start the UI:

```bash
docker compose up -d web
```

In S3-enabled environments, cached extraction artifacts are restored when possible, reducing repeated Textract processing.

---

## 13. Key design decisions

### Why semantic search instead of keyword search alone?

Regulatory descriptions often use terminology different from an ordinary buyer description.

A user may write:

```text
Batterie lithium-ion rechargeable pour véhicule électrique
```

while the tariff nomenclature uses:

```text
Accumulateurs électriques — au lithium-ion
```

Pure keyword matching may miss this relationship or incorrectly favour other records containing the word “lithium”.

Semantic retrieval provides plausible candidates, while deterministic logic and LLM reasoning determine whether those candidates actually describe the same product.

### Why not let the LLM calculate everything?

Tariff codes, duty rates, origin rules, and legal sources are regulatory facts.

The LLM is therefore used primarily for semantic ambiguity resolution. Structured data remains authoritative for:

* tariff codes;
* standard duty rates;
* FTA tariff information;
* origin rules;
* source references;
* numeric calculations.

---

## 14. Current limitations

This is a prototype rather than a complete customs-classification system.

Important limitations include:

* only a subset of the supplied PDF pages is ingested;
* product descriptions may lack enough technical detail to determine an NC8 code;
* FTA origin cannot be verified without manufacturing/material information;
* historical FTA tariff reconciliation can remain uncertain when older tariff branches require product characteristics absent from the request;
* tariff dismantling categories are not interpreted unless the ingested evidence directly supports the applicable preferential rate;
* the current runtime scope focuses primarily on customs classification, tariffs, FTA rules, and source-backed calculations rather than implementing every sector-specific regulatory regime.

When the available evidence is insufficient, the preferred behaviour is to return uncertainty rather than generate an unsupported regulatory conclusion.

---

## Technology

```text
Python 3.12+
PostgreSQL
pgvector
Amazon ECS / Fargate
Amazon S3
Amazon Bedrock
Amazon Textract
Streamlit
Docker
```

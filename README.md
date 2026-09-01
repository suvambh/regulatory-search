# Regulatory Engine

Cloud-based prototype for EU import tariff classification, preferential trade analysis, and selected product-specific regulatory requirements.

The system takes a product description, exporter country, importer country, and goods value, then retrieves and evaluates the relevant customs and regulatory context from a controlled regulatory corpus.

The prototype combines:

* deterministic regulatory logic;
* PostgreSQL and pgvector semantic retrieval;
* Amazon Bedrock embeddings and bounded LLM reasoning;
* Amazon Textract document extraction;
* source-backed tariff and regulatory evidence;
* explicit uncertainty when the available product information is insufficient.

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
* whether a supported preferential trade agreement applies;
* the applicable preferential origin rule;
* the relevant historical FTA tariff line when nomenclature versions differ;
* the preferential tariff when directly supported by the available legal evidence;
* selected additional regulatory requirements, currently including EU medical-device classification under Regulation (EU) 2017/745.

The system is deliberately conservative.

If the supplied product description does not support an exact classification, tariff calculation, preferential origin conclusion, or medical-device classification, the engine returns an uncertainty status rather than inventing a result.

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
  ├── Streamlit UI
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

**Amazon ECS / Fargate**

Runs the packaged Python application, Streamlit interface, and one-off ingestion tasks.

**Aurora PostgreSQL + pgvector**

Stores structured tariff data, FTA provisions, rules of origin, historical tariff schedules, medical regulatory provisions, and semantic embeddings.

**Amazon S3**

Stores the regulatory PDF corpus and reusable extraction and cleaning artifacts.

The storage convention is approximately:

```text
corpus/... → s3://.../raw/...

data/...   → s3://.../processed/...
```

**Amazon Textract**

Extracts text and structured information from selected PDF pages during ingestion.

**Amazon Bedrock**

Provides multilingual embeddings and bounded LLM reasoning for classification and ambiguity resolution.

---

## 3. Runtime analysis approach

The application avoids using an LLM when deterministic regulatory logic is sufficient.

The main runtime pattern is:

```text
Structured lookup / filtering
          ↓
Semantic candidate retrieval
          ↓
Bounded classification reasoning
          ↓
Deterministic tariff / regulatory logic
          ↓
Source-backed result
```

The LLM does not act as the authoritative regulatory database.

Structured records remain authoritative for tariff codes, duty rates, legal provisions, origin rules, regulatory rules, and source references.

---

## 4. NC classification

Product descriptions are embedded and compared with indexed EU Combined Nomenclature records.

Semantic similarity is used only for retrieval.

The highest similarity result is not automatically accepted.

Instead:

```text
Product description
        ↓
Bedrock embedding
        ↓
pgvector candidate retrieval
        ↓
Candidate hierarchy evaluation
        ↓
Bounded classifier
        ↓
SUPPORTED / UNCERTAIN_CLASSIFICATION
```

The classifier evaluates the complete tariff hierarchy rather than only the final leaf description.

A leaf-level match is valid only when the required parent-level restrictions are also supported.

This prevents a strong keyword match from overriding missing hierarchical conditions.

### Example

A rechargeable lithium-ion vehicle battery may retrieve both rechargeable accumulators and primary lithium batteries.

The reasoning layer must distinguish:

```text
rechargeable accumulator
```

from:

```text
primary battery
```

before selecting a final NC code.

---

## 5. Classification uncertainty

The engine does not assume that the top retrieved candidates represent every legally possible tariff branch.

For example:

```text
Câbles électriques en cuivre isolés
```

can be narrowed to HS heading:

```text
8544
```

but the exact NC8 classification depends on additional characteristics such as voltage and construction.

The engine therefore uses:

```text
Known HS4 + uncertain NC8
        ↓
standard rate not determined
        ↓
missing product information returned
```

It does not calculate a customs duty simply because the retrieved candidates happen to share a similar rate.

---

## 6. Tariff calculation

When a supported NC8 classification is available, tariff calculation is deterministic.

Example:

```text
Value: €8,000
Rate: 2.7%

Duty = €8,000 × 2.7%
     = €216
```

The engine also preserves non-ad-valorem tariff expressions.

For example:

```text
124.5 EUR / 100 kg net
```

is not converted into an artificial percentage.

If shipment weight is missing, the engine returns the missing information required to complete the calculation.

---

## 7. Preferential trade agreements

The prototype currently contains structured support for:

```text
EU–Morocco
EU–South Korea
```

FTA analysis separates several questions:

```text
Does a supported agreement exist?
        ↓
What legal provision applies?
        ↓
What rule of origin applies?
        ↓
Can origin be verified?
        ↓
What historical tariff line applies?
        ↓
Can a preferential rate be determined?
```

The country of export alone is not treated as proof of preferential origin.

Where manufacturing and material-value information is missing, origin remains:

```text
NOT_VERIFIED
```

### Morocco

The EU–Morocco agreement contains direct legal support for duty-free treatment of qualifying originating industrial products.

The engine can therefore determine a preferential 0% rate when the relevant legal evidence applies, while still marking origin as unverified if the scenario lacks production data.

### South Korea

The EU–South Korea FTA uses historical tariff nomenclature.

The engine retrieves the relevant historical tariff schedule but keeps the historical code separate from the current NC classification.

For example:

```text
Current EU NC code
        ↓
historical FTA tariff family
        ↓
historical tariff line
        ↓
base rate + staging category
```

A historical FTA code never replaces the current NC classification.

---

## 8. Historical FTA reconciliation

FTA tariff schedules can use an older nomenclature than the current EU NC.

Exact code equality is therefore not required.

The reconciliation flow is:

```text
Current NC classification
        ↓
Relevant historical HS family
        ↓
Semantic retrieval of historical tariff lines
        ↓
Bounded comparison of product meaning
        ↓
Historical schedule evidence
```

This is particularly important for the EU–South Korea agreement.

Historical tariff reconciliation is used only to retrieve the appropriate FTA schedule entry.

It does not modify the current customs classification.

---

## 9. Medical-device regulation

The prototype also supports selected regulatory analysis under:

```text
Regulation (EU) 2017/745
Medical Device Regulation — MDR
```

Medical-device analysis is intentionally narrow and source-grounded rather than a generic full-regulation RAG system.

The runtime flow is:

```text
Product
  ↓
Structured MDR provisions
  ↓
Applicability assessment
  ↓
Annex VIII classification rules
  ↓
Bounded Bedrock reasoning
  ↓
MDR class + exact legal sources
```

The system currently retrieves:

* selected Article 2 definitions;
* Article 19 — EU declaration of conformity;
* Article 20 — CE marking;
* Article 51 — classification;
* Articles 52–53 — conformity assessment;
* Annex II — technical documentation;
* Annex IV — EU declaration of conformity;
* Annex VIII — classification context and Rules 1–22.

### Example: pulse oximeter

```text
Product:
Digital pulse oximeter measuring SpO2 and heart rate

NC:
90181910

Standard duty:
0%

MDR:
Class IIa

Classification rule:
Annex VIII — Rule 10
```

### Example: hip prosthesis

```text
Product:
Titanium hip prosthesis

NC:
90213100

Standard duty:
0%

MDR:
Class III

Classification rule:
Annex VIII — Rule 8
```

The UI displays only the essential regulatory conclusion and practical requirements by default.

Detailed definitions, legal provisions, and source excerpts remain accessible through expandable source sections and the technical result.

---

## 10. Regulatory data

The prototype uses a deliberately limited subset of the supplied regulatory corpus covering the required evaluation scenarios.

### Main database tables

```text
tariff_items
fta_chunks
fta_origin_rules
fta_tariff_lines
medical_provisions
```

### `tariff_items`

Contains:

* current NC codes;
* tariff descriptions;
* hierarchy information;
* standard tariff data;
* source evidence;
* semantic embeddings.

### `fta_chunks`

Contains selected legal provisions from supported trade agreements.

### `fta_origin_rules`

Contains product-specific rules of origin indexed primarily by agreement and HS heading.

### `fta_tariff_lines`

Contains historical FTA tariff schedules used for nomenclature reconciliation.

### `medical_provisions`

Contains structured MDR evidence including:

* definitions;
* articles;
* Annex VIII classification context;
* classification rules;
* selected annex excerpts;
* source page and section;
* source excerpt.

---

## 11. Cached ingestion artifacts

Reusable intermediate data is stored in S3.

Typical structure:

```text
raw/
└── regulatory PDFs

processed/
├── raw/
│   ├── nc/
│   ├── fta/
│   └── medical/
│
└── cleaned/
    ├── nc/
    ├── fta/
    └── medical/
```

This avoids repeating Textract processing unnecessarily.

Medical ingestion, for example, stores:

```text
processed/raw/medical/mdr/
processed/cleaned/medical/mdr/provisions.json
```

Embeddings can also be reused when the underlying descriptions have not changed.

---

## 12. Repository structure

```text
app/
└── streamlit_app.py

config/
├── fta_agreements.json
├── medical_regulations.json
└── nc.json

corpus/
├── nc2024.pdf
├── korea.pdf
├── maroc.pdf
└── medical.pdf

database/
└── migrations/
    ├── 001_...
    └── 002_create_medical_tables.sql

scripts/
├── evaluate_scenarios.py
├── inspect_fta.py
└── scan_pdf_pages.py

src/regulatory_engine/
├── application/
│   └── evaluate.py
│
├── classification/
│
├── fta/
│
├── medical/
│   ├── classifier.py
│   └── service.py
│
├── infrastructure/
│   ├── bedrock.py
│   ├── database.py
│   ├── embeddings.py
│   ├── storage.py
│   └── textract.py
│
├── ingestion/
│   ├── common/
│   ├── nc/
│   ├── fta/
│   └── medical/
│       ├── extract.py
│       ├── clean.py
│       └── load.py
│
├── models/
│
├── repositories/
│   └── medical_repository.py
│
└── tariff/

tests/
├── integration/
└── manual/
```

The main application entry point is:

```python
evaluate_import(request: ImportRequest)
```

The Streamlit UI and evaluation scripts use the same application layer.

---

## 13. Local setup

### Prerequisites

* Python 3.12+
* Docker
* Docker Compose
* AWS CLI
* AWS credentials with access to the required Bedrock and Textract services in `eu-west-3`

Configure AWS credentials:

```bash
aws configure
```

Verify access:

```bash
aws sts get-caller-identity
```

### Build containers

```bash
docker compose build web
docker compose --profile ingestion build ingestion
```

### Start PostgreSQL

```bash
docker compose up -d db
```

Check status:

```bash
docker compose ps
```

Local PostgreSQL is exposed on port:

```text
5433
```

---

## 14. Build the regulatory database

### Apply migrations

The repository contains SQL migrations under:

```text
database/migrations/
```

The Python migration helper can be executed through the ingestion container:

```bash
docker compose --profile ingestion run --rm ingestion \
  python -c \
  "from regulatory_engine.infrastructure.migrations import run_migrations; run_migrations()"
```

---

## 15. NC ingestion

Run:

```bash
docker compose --profile ingestion run --rm ingestion \
  python -m regulatory_engine.ingestion.nc.run
```

The NC pipeline performs:

```text
selected-page extraction / cache restoration
        ↓
hierarchy reconstruction
        ↓
tariff cleaning
        ↓
PostgreSQL loading
        ↓
missing embedding generation
```

Only the pages required for the prototype scenarios need to be processed.

---

## 16. FTA ingestion

Run:

```bash
docker compose --profile ingestion run --rm ingestion \
  python -m regulatory_engine.ingestion.fta.run
```

The FTA pipeline performs:

```text
tariff and origin extraction
        ↓
legal provision extraction
        ↓
legal cleaning
        ↓
origin-rule cleaning
        ↓
historical tariff cleaning
        ↓
PostgreSQL loading
        ↓
historical tariff embeddings
```

---

## 17. Medical ingestion

Medical ingestion is separated into three explicit stages.

### Extract

```bash
docker compose --profile ingestion run --rm ingestion \
  python -m regulatory_engine.ingestion.medical.extract
```

### Clean

```bash
docker compose --profile ingestion run --rm ingestion \
  python -m regulatory_engine.ingestion.medical.clean --force
```

### Load

```bash
docker compose --profile ingestion run --rm ingestion \
  python -m regulatory_engine.ingestion.medical.load
```

The pipeline is:

```text
medical.pdf
    ↓
selected page extraction
    ↓
structural cleaning
    ↓
provisions.json
    ↓
medical_provisions
```

A successful prototype load currently produces structured definitions, articles, annex excerpts, and all Annex VIII classification rules required by the application.

---

## 18. Run the application

Start Streamlit:

```bash
docker compose up -d web
```

Open:

```text
http://localhost:8501
```

View logs:

```bash
docker compose logs -f web
```

The AWS deployment exposes the same application through an Application Load Balancer.

---

## 19. Evaluation scenarios

The seven supplied scenarios can be executed directly against the application layer:

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

scenario_1.json
scenario_2.json
scenario_3.json
scenario_4.json
scenario_5.json
scenario_6.json
scenario_7.json
```

The scenarios cover:

1. Laptop computer imported from China
2. Electrical cables imported from Morocco
3. LCD monitor imported from South Korea
4. Pulse oximeter
5. Titanium hip prosthesis
6. Extra virgin olive oil
7. Electric-vehicle lithium-ion battery

These scenarios are also used as regression tests while modifying retrieval and classification behaviour.

---

## 20. Example behaviours

### Standard import

Input:

```text
Ordinateur portable 14 pouces
Chine → France
€500
```

Result:

```text
NC 84713000
Standard duty: 0%
Estimated duty: €0
```

### Classification uncertainty

Input:

```text
Câbles électriques en cuivre isolés
Maroc → France
```

Result:

```text
HS4: 8544
Exact NC8: unresolved
Standard tariff: not calculated
```

The Morocco agreement and relevant origin rule can still be retrieved independently.

### Specific tariff

Input:

```text
Huile d'olive vierge extra bio
```

Result:

```text
NC 15092000
Tariff: 124.5 EUR / 100 kg net
```

The engine requests weight rather than converting this into an unsupported percentage.

### Medical-device analysis

Input:

```text
Prothèse de hanche en titane
```

Result:

```text
NC 90213100
Standard duty: 0%
MDR Class III
Annex VIII — Rule 8
```

---

## 21. AWS deployment

The production prototype uses:

```text
Application Load Balancer
        ↓
ECS service
        ↓
Fargate web task
        ↓
Aurora PostgreSQL
```

The same container image can also be used for one-off ingestion tasks.

This separates:

```text
runtime requests
```

from:

```text
document ingestion
```

which prevents expensive Textract/document-processing work from occurring during user requests.

### Deployment pattern

```text
Build Docker image
        ↓
Push to Amazon ECR
        ↓
Register new ECS task-definition revision
        ↓
Run required one-off ingestion tasks
        ↓
Update ECS service
        ↓
ALB health check
```

For ingestion tasks, shell commands should fail immediately when any step fails:

```bash
set -e
```

This prevents an extraction or loading failure from being incorrectly reported as a successful ECS task.

---

## 22. Database verification

To inspect loaded records locally:

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
    SELECT 'fta_tariff_lines', COUNT(*) FROM fta_tariff_lines
    UNION ALL
    SELECT 'medical_provisions', COUNT(*) FROM medical_provisions;
  "
```

Medical rows can also be inspected with:

```sql
SELECT
    provision_id,
    provision_type,
    provision_code,
    source_page
FROM medical_provisions
ORDER BY provision_id;
```

---

## 23. Rebuild from scratch

Delete the local database:

```bash
docker compose down -v
```

Start a fresh PostgreSQL instance:

```bash
docker compose up -d db
```

Apply migrations:

```bash
docker compose --profile ingestion run --rm ingestion \
  python -c \
  "from regulatory_engine.infrastructure.migrations import run_migrations; run_migrations()"
```

Run NC ingestion:

```bash
docker compose --profile ingestion run --rm ingestion \
  python -m regulatory_engine.ingestion.nc.run
```

Run FTA ingestion:

```bash
docker compose --profile ingestion run --rm ingestion \
  python -m regulatory_engine.ingestion.fta.run
```

Run medical ingestion:

```bash
docker compose --profile ingestion run --rm ingestion \
  python -m regulatory_engine.ingestion.medical.extract

docker compose --profile ingestion run --rm ingestion \
  python -m regulatory_engine.ingestion.medical.clean --force

docker compose --profile ingestion run --rm ingestion \
  python -m regulatory_engine.ingestion.medical.load
```

Start the application:

```bash
docker compose up -d web
```

In an S3-enabled environment, reusable extraction and cleaning artifacts are restored where available.

---

## 24. Key design decisions

### Semantic retrieval is not legal evidence

Embedding similarity is used only to identify plausible records.

It is not treated as evidence that a tariff code or regulatory rule applies.

### The LLM cannot invent tariff codes

The NC classifier may only select from the retrieved candidate set.

### Hierarchical restrictions are cumulative

A leaf-level tariff description cannot be accepted while required parent-level conditions remain unsupported.

### Structured data is authoritative

The following remain deterministic or database-backed:

* NC codes;
* standard duty rates;
* tariff expressions;
* FTA legal provisions;
* rules of origin;
* historical tariff schedule entries;
* MDR provisions and rules;
* source pages;
* numeric tariff calculations.

### Current and historical tariff codes are separate

Historical FTA nomenclature is used only for the relevant trade-agreement schedule.

It never replaces the current NC code.

### Uncertainty is a valid result

When information is missing, the system reports what additional product information is required instead of generating an unsupported classification or duty.

---

## 25. Current limitations

This is a prototype rather than a complete customs or regulatory-compliance platform.

Important limitations include:

* only a selected subset of the supplied regulatory corpus is ingested;
* product descriptions may lack enough technical detail to determine an exact NC8 code;
* FTA origin cannot be independently verified without manufacturing and material-value information;
* historical FTA tariff reconciliation can remain uncertain when old nomenclature requires characteristics absent from the request;
* EU–South Korea tariff staging categories are retrieved but are not interpreted unless the ingested legal evidence directly supports the applicable preferential rate;
* sparse monitor descriptions can remain difficult to distinguish between closely related current NC branches;
* the MDR module covers the selected prototype requirements and classification rules rather than implementing the entire medical-device regulatory lifecycle;
* regulatory results are intended as source-backed decision support, not as a substitute for a binding customs or regulatory determination.

When evidence is insufficient, the preferred behaviour is to return uncertainty.

---

## 26. Technology

```text
Python 3.12+
PostgreSQL
pgvector
Amazon Aurora PostgreSQL
Amazon ECS / Fargate
Amazon ECR
Application Load Balancer
Amazon S3
Amazon Bedrock
Amazon Textract
Streamlit
Docker
Docker Compose
```

---

## 27. Prototype scope

The final prototype demonstrates:

```text
Natural-language product input
        ↓
Current EU NC retrieval and classification
        ↓
Standard tariff calculation
        ↓
Preferential agreement analysis
        ↓
Rules-of-origin evidence
        ↓
Historical FTA nomenclature reconciliation
        ↓
Selected MDR regulatory classification
        ↓
Source-backed result in Streamlit
```

The implementation prioritizes traceability, conservative decision-making, and reproducible regulatory evidence over unsupported automation.

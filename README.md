# Regulatory Engine

Cloud-based prototype for EU import tariff classification, preferential trade analysis, and selected medical-device regulatory requirements.

The system takes a product description, exporter country, importer country, and goods value, then retrieves and evaluates the relevant customs and regulatory context from a controlled corpus.

It combines deterministic regulatory logic, PostgreSQL/pgvector semantic retrieval, Amazon Bedrock reasoning, Amazon Textract extraction, and source-backed regulatory evidence.

The system is deliberately conservative: when the available information is insufficient, it returns uncertainty rather than inventing a classification, tariff, origin status, or regulatory conclusion.

---

## 1. Scope

The prototype evaluates:

* EU Combined Nomenclature (NC) classification;
* standard customs-duty rate;
* estimated customs duty where enough information is available;
* supported preferential trade agreements;
* product-specific rules of origin;
* historical FTA tariff schedules where nomenclature versions differ;
* selected requirements under Regulation (EU) 2017/745 for medical devices.

The implementation is built around seven evaluation scenarios covering standard imports, preferential trade, medical devices, specific tariffs, and classification uncertainty.

The main application entry point is:

```python
evaluate_import(request: ImportRequest)
```

The same application layer is used by the Streamlit interface and by the evaluation scripts.

---

## 2. NC classification

Product descriptions are embedded and compared with indexed EU Combined Nomenclature records stored in PostgreSQL with pgvector.

The highest semantic similarity result is not automatically selected.

The runtime flow is:

```text
Product description
        ↓
Bedrock embedding
        ↓
pgvector candidate retrieval
        ↓
Hierarchy-aware classification
        ↓
SUPPORTED / UNCERTAIN_CLASSIFICATION
```

Semantic similarity is used only to retrieve plausible candidates.

The classifier evaluates the complete NC hierarchy and must support the relevant parent restrictions before selecting a final code.

A leaf-level keyword match is therefore not sufficient when higher-level conditions remain unknown.

The engine also avoids calculating a tariff when the exact NC8 classification is unresolved.

If only a broader HS heading can be established, the system returns the missing product characteristics required to distinguish the remaining branches.

Tariff calculations are deterministic once a supported classification is available.

Non-percentage tariffs are preserved in their original form. If a tariff depends on quantity or weight, the engine requests that information instead of converting the tariff into an artificial percentage.

---

## 3. Preferential trade agreements

The prototype currently contains structured support for:

```text
EU–Morocco
EU–South Korea
```

FTA analysis separates:

```text
Supported agreement
        ↓
Legal basis
        ↓
Rule of origin
        ↓
Origin verification
        ↓
Tariff schedule
        ↓
Preferential rate
```

The export country alone is not treated as proof of preferential origin.

If manufacturing and material-value information is missing, the origin status remains:

```text
NOT_VERIFIED
```

### EU–Morocco

The system retrieves the relevant legal provision and product-specific rule of origin.

Where the agreement directly supports duty-free treatment for qualifying originating products, the preferential rate can be determined while origin remains explicitly unverified from the scenario data.

### EU–South Korea

The Korea agreement uses an older tariff nomenclature than the current EU NC.

The system therefore keeps two concepts separate:

```text
Current EU NC classification
```

and:

```text
Historical FTA tariff line
```

The reconciliation flow is:

```text
Current NC
    ↓
Historical HS family
    ↓
Historical tariff candidates
    ↓
Bounded semantic reconciliation
    ↓
FTA tariff schedule evidence
```

Historical tariff codes are used only for the FTA schedule and never replace the current NC classification.

The current prototype retrieves the historical base rate and staging category, but does not interpret tariff staging categories unless the available legal evidence directly supports the applicable preferential rate.

---

## 4. Medical-device regulation

The prototype supports selected analysis under:

```text
Regulation (EU) 2017/745
Medical Device Regulation — MDR
```

The medical module is intentionally narrow and source-grounded.

The runtime flow is:

```text
Product
  ↓
MDR applicability evidence
  ↓
Annex VIII classification rules
  ↓
Bounded Bedrock reasoning
  ↓
MDR class
  ↓
Exact regulatory sources
```

The structured MDR corpus contains selected:

* Article 2 definitions;
* Article 19 — EU declaration of conformity;
* Article 20 — CE marking;
* Article 51 — classification;
* Articles 52–53 — conformity assessment;
* Annex II — technical documentation;
* Annex IV — declaration of conformity;
* Annex VIII classification context and Rules 1–22.

The result includes:

* whether MDR analysis applies;
* MDR class;
* applicable Annex VIII rule;
* short reasoning;
* missing information where classification cannot be confirmed;
* source page and regulatory reference.

The Streamlit interface shows only the essential conclusion and practical requirements by default, while detailed legal evidence remains available through expandable source sections.

---

## 5. Regulatory data and ingestion

The main PostgreSQL tables are:

```text
tariff_items
fta_chunks
fta_origin_rules
fta_tariff_lines
medical_provisions
```

The ingestion pattern is:

```text
Regulatory PDF
      ↓
Selected-page extraction
      ↓
Structural cleaning
      ↓
Structured records
      ↓
PostgreSQL
      ↓
Embeddings where required
```

Amazon Textract is used during document ingestion.

Amazon S3 stores:

* source regulatory PDFs;
* raw extracted pages;
* cleaned intermediate artifacts.

This allows extraction results to be reused instead of repeatedly processing the same documents.

Ingestion is separate from runtime analysis. User requests only retrieve the structured evidence needed for the current analysis.

---

## 6. AWS architecture

The deployed application uses:

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
  └── regulatory_engine
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
Embeddings:
cohere.embed-multilingual-v3

Classification / reasoning:
eu.amazon.nova-pro-v1:0
```

Amazon ECS/Fargate runs both the web application and one-off ingestion tasks.

Aurora PostgreSQL stores structured regulatory data and embeddings.

Amazon Bedrock provides multilingual embeddings and bounded classification reasoning.

Amazon Textract is used for selected regulatory-document extraction.

Amazon S3 stores the corpus and reusable processing artifacts.

---

## 7. Local setup

Prerequisites:

* Python 3.12+
* Docker
* Docker Compose
* AWS CLI
* AWS credentials with access to Bedrock and Textract in `eu-west-3`

Configure AWS:

```bash
aws configure
aws sts get-caller-identity
```

Build the application:

```bash
docker compose build web
docker compose --profile ingestion build ingestion
```

Start PostgreSQL:

```bash
docker compose up -d db
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

Start the UI:

```bash
docker compose up -d web
```

Open:

```text
http://localhost:8501
```

Run the regression scenarios:

```bash
python scripts/evaluate_scenarios.py
```

---

## 8. Deployment

The deployment flow is:

```text
Build Docker image
        ↓
Push to Amazon ECR
        ↓
Register ECS task definition
        ↓
Run required ingestion tasks
        ↓
Update ECS service
        ↓
Verify ALB / ECS health
```

Ingestion runs as a one-off Fargate task rather than inside user requests.

Shell-based ingestion commands should use:

```bash
set -e
```

so a failed extraction or database load causes the task to fail immediately.

---

## 9. Key design decisions

### Structured evidence is authoritative

The LLM does not invent:

* tariff codes;
* duty rates;
* origin rules;
* FTA provisions;
* MDR rules;
* source references.

### Semantic search is retrieval only

Embedding similarity identifies candidate records but is not treated as regulatory evidence.

### Hierarchy is cumulative

A final NC code must satisfy the required restrictions inherited from its parent levels.

### Current and historical codes remain separate

Historical FTA tariff codes are used only to reconcile older trade-agreement schedules.

### Uncertainty is an expected result

Missing technical information is surfaced explicitly instead of being replaced with assumptions.

---

## 10. Current limitations

This is a prototype rather than a complete customs or regulatory-compliance platform.

Current limitations include:

* only selected parts of the supplied corpus are ingested;
* sparse product descriptions may not support an exact NC8 classification;
* preferential origin cannot be independently verified without manufacturing information;
* historical tariff reconciliation may remain uncertain;
* EU–South Korea tariff staging categories are retrieved but not fully interpreted;
* some closely related NC branches require additional intended-use information;
* the MDR module covers selected classification and conformity requirements rather than the complete medical-device regulatory lifecycle;
* outputs are decision-support information rather than binding customs or regulatory determinations.

When the evidence is insufficient, the preferred behaviour is to return uncertainty.

---

## Technology

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

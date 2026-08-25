## Technical Summary

The prototype implements a local end-to-end pipeline for extracting, indexing, and searching EU Combined Nomenclature 2024 tariff data.

### Stack

* **Python** — application and ingestion scripts
* **PyMuPDF** — renders selected PDF pages as images
* **AWS Textract** — extracts tariff tables from the rendered NC2024 pages
* **pandas** — cleans and normalizes extracted CSV data
* **PostgreSQL** — stores structured tariff records
* **pgvector** — stores and searches 1024-dimensional embeddings
* **psycopg** — PostgreSQL access from Python
* **AWS Bedrock**

  * **Cohere Embed Multilingual v3** — document and query embeddings
  * **Amazon Nova Micro** — final candidate selection and explanation
* **Docker** — runs PostgreSQL locally

### Data Pipeline

```text
NC2024 PDF
   ↓
PyMuPDF
   ↓
AWS Textract
   ↓
Raw CSV
   ↓
pandas cleaning
   ↓
PostgreSQL + pgvector
   ↓
Cohere embeddings
```

Each tariff record contains the NC code, description, numeric and textual duty information, supplementary unit, source metadata, and a `VECTOR(1024)` embedding.

### Search Pipeline

```text
Product description
   ↓
Cohere search_query embedding
   ↓
pgvector cosine similarity
   ↓
Top NC candidates
   ↓
Amazon Nova Micro
   ↓
Selected NC code + explanation
```

The vector search retrieves semantically relevant tariff entries, while Nova Micro performs a second-stage classification over the retrieved candidates. This avoids relying only on keyword matching or choosing the highest vector similarity score automatically.

The complete local pipeline has been successfully tested from PDF extraction through database loading, embedding generation, vector retrieval, and LLM-assisted NC classification.

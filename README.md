# regulatory-search

The current prototype implements an end-to-end regulatory tariff search pipeline for the EU Combined Nomenclature 2024.

The NC2024 PDF is processed page by page with **PyMuPDF** and **AWS Textract**, which extracts tariff tables into CSV. A cleaning step normalizes NC codes, descriptions, duty rates, supplementary units, and source metadata before loading the structured rows into a local **PostgreSQL** database running in Docker.

The `tariff_items` table stores the tariff data together with a `VECTOR(1024)` column provided by **pgvector**. Each tariff description is embedded using **AWS Bedrock Cohere Embed Multilingual v3** and stored in PostgreSQL.

At query time, the user product description is embedded with the same Cohere model using `search_query`. PostgreSQL performs a cosine-similarity search against the stored tariff embeddings to retrieve the most relevant NC candidates. These candidates are then passed to **Amazon Nova Micro** through Bedrock, which selects the most appropriate NC code based on the actual product and tariff descriptions rather than relying solely on vector similarity.

The current working flow is therefore:

```text
NC2024 PDF
   ↓
PyMuPDF + AWS Textract
   ↓
Raw CSV
   ↓
Cleaning / normalization
   ↓
PostgreSQL + pgvector
   ↓
Cohere multilingual embeddings
   ↓
Semantic candidate retrieval
   ↓
Amazon Nova Micro classification
   ↓
NC code + explanation
```

The full local pipeline has been tested successfully with the example **“Ordinateur portable 14 pouces”**, including extraction, database loading, embedding generation, vector retrieval, and LLM-based candidate selection.

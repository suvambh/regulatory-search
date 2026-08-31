## Executive Summary

International buyers often lack a simple and reliable way to understand the true cost of importing goods. Customs classification, duties, trade-agreement preferences, and regulatory requirements are distributed across complex official documents, making the research process slow and difficult to navigate.

This project demonstrates a cloud-based regulatory research system that automates this process. From a product description and import context, the system identifies the relevant customs and regulatory information, determines the applicable tariff treatment, estimates quantifiable additional costs, and provides the exact official sources supporting its conclusions. Where the available information is insufficient to produce a reliable calculation, the system explicitly identifies the missing information rather than making unsupported assumptions.

The prototype is evaluated across seven representative scenarios covering standard imports, preferential trade agreements, historical tariff nomenclatures, regulated medical products, food products, and technically detailed goods. The same approach is designed to support orders containing multiple product types, allowing their regulatory impacts to ultimately be consolidated into a single view for the buyer.

The solution combines structured regulatory data and deterministic rules with semantic retrieval and AI-based interpretation where ambiguity remains. This approach aims to balance answer quality, traceability, response time, scalability, and operating cost while providing a clear path for progressively expanding the regulatory coverage.


## Approach

The solution is designed around two main stages: **building a structured regulatory knowledge base** (too complicated, feels like jargon, use simpler terms and explain what is a knowledge base) and **using that knowledge to evaluate a buyer's product and import context**.

### 1. Build a structured regulatory knowledge base

The provided regulatory documents are processed through ingestion pipelines. Their content is extracted, cleaned, structured, and stored in a data model designed for efficient retrieval.

Different types of information are stored according to their purpose. For example:

* The **Combined Nomenclature** is transformed into structured records containing NC codes, product descriptions, tariff rates, hierarchy information, and source references.
* **Free Trade Agreements** are processed into records containing tariff lines, applicable rules, agreement provisions, and supporting legal references.

Relevant textual fields are also converted into vector representations, allowing the system to search by both meaning/semantic match and keywords.

This data model is intended to become richer over time. Additional relationships, classifications, legal rules, product attributes, and historical information can be added as the regulatory coverage grows. The richer the structured data becomes, the easier it is to provide AI models with precise and relevant context instead of asking them to interpret entire documents.

The ingestion architecture is also designed so that **new documents and regulatory domains can be added without redesigning the overall system**.

### 2. Classify the buyer's product

When a buyer submits a product, the first step is to identify its most appropriate **current EU NC classification**.

The product description is compared semantically with the descriptions in the nomenclature. The system retrieves the most relevant candidates and determines which classification best represents the product.

This classification provides the starting point for tariff and regulatory analysis.

### 3. Determine the applicable tariff treatment

Using the product classification together with the exporting and importing countries, the system determines which tariff treatment may apply.

If no relevant preferential agreement is available, the standard tariff can be retrieved directly from the Combined Nomenclature data.

If a relevant trade agreement exists, the system retrieves the corresponding tariff lines and agreement rules and evaluates whether they apply to the product.


### 4. Retrieve additional regulatory requirements

For products that may be subject to additional regulations, such as medical-device or CE requirements, the system uses **Amazon Bedrock Knowledge Bases** to retrieve the most relevant provisions from the cleaned regulatory documents.

The application provides the product context, Bedrock retrieves the relevant legal passages, and the AI layer determines which requirements are applicable. This allows the system to add regulatory context without requiring the full document to be processed for every request.


### 5. Apply rules and produce a consolidated result

Once the relevant tariff, agreement, and regulatory information has been identified, the system provides the AI layer with a **focused and structured context** from which the applicable rules can be interpreted.

The final result can then consolidate:

* the product classification,
* the applicable tariff,
* potential preferential treatment,
* relevant regulatory requirements,
* the estimated additional import cost,
* and the exact official sources supporting the conclusions.

The long-term objective is to progressively move knowledge into the structured data model. **AI remains responsible for interpretation and ambiguity, while deterministic data and rules handle cases that can be resolved reliably.** As the knowledge base becomes richer, the system becomes more consistent, explainable, scalable, and cost-efficient. 


## Prototype Scope

The prototype focuses on the core capabilities required to demonstrate automated import-cost and regulatory analysis across the seven scenarios defined in the exercise.

### Included in the prototype

The current scope covers:

* **Product classification** against the EU Combined Nomenclature, using semantic search to identify the most relevant NC code.
* **Standard customs-duty retrieval** from the 2024 Combined Nomenclature.
* **Preferential tariff treatment** for the trade agreements covered by the prototype, notably Morocco and South Korea.
* **FTA nomenclature reconciliation** where the tariff codes used in an agreement differ from the current NC classification.
* **Regulatory retrieval** for selected medical-device and CE-related requirements relevant to the test scenarios.
* **Cost estimation** based on the applicable tariff treatment and the declared value of the goods.
* **Source traceability**, with the result linked back to the relevant regulatory document, section, and supporting text.
* A user-facing interface that brings these elements together into a single result for the buyer.

### Intentionally limited scope

The prototype is not intended to provide complete customs or legal-compliance coverage.

It does not attempt to model every possible customs rule, trade agreement, origin requirement, conformity obligation, tax, transport cost, or import-related fee. Regulatory coverage is limited to the documents and scenarios required for the exercise, with selected sections ingested where they are sufficient to demonstrate the approach.

The objective is therefore to validate the **core decision-support model**: classify the product, retrieve the relevant tariff and regulatory information, apply the appropriate rules, calculate the impact, and provide evidence for the result.

### Designed for expansion

The prototype is deliberately structured so that additional NC versions, trade agreements, regulatory domains, and product categories can be added progressively.

As the underlying data model becomes richer, more decisions can be handled deterministically, while AI can be focused on the areas where interpretation or ambiguity genuinely remains. This provides a path from a targeted prototype toward a broader and more reliable regulatory platform.


## Architecture

The application is containerized and deployed on Amazon ECS, with S3 storing the regulatory corpus, PostgreSQL providing the authoritative structured regulatory data, and Amazon Bedrock providing semantic retrieval and AI reasoning. Documents are processed once during ingestion, while buyer requests retrieve only the structured data and legal context required for each analysis.

                         ┌──────────────────────┐
                         │        User          │
                         │   Streamlit Web UI   │
                         └──────────┬───────────┘
                                    │ HTTPS
                                    ▼
                         ┌──────────────────────┐
                         │ Application Load     │
                         │ Balancer             │
                         └──────────┬───────────┘
                                    │
                                    ▼
                ┌────────────────────────────────────┐
                │        Amazon ECS / Fargate        │
                │                                    │
                │  Container running Python package  │
                │  regulatory_engine                 │
                │                                    │
                │  • Streamlit UI                    │
                │  • Product classification          │
                │  • Tariff / FTA logic              │
                │  • Cost calculation                │
                │  • Bedrock retrieval calls         │
                │  • AI orchestration                │
                └──────┬─────────┬─────────┬─────────┘
                       │         │         │
              ┌────────┘         │         └──────────────┐
              ▼                  ▼                        ▼
     ┌─────────────────┐  ┌────────────────┐    ┌─────────────────┐
     │ PostgreSQL      │  │ Amazon Bedrock │    │ Amazon S3       │
     │ RDS / Aurora    │  │                │    │                 │
     │                 │  │ • LLMs         │    │ • Raw PDFs      │
     │ • NC codes      │  │ • Embeddings   │    │ • Cleaned .md   │
     │ • Tariffs       │  │ • Knowledge    │    │ • Source files  │
     │ • FTA lines     │  │   Bases        │    │                 │
     │ • Agreements    │  └───────┬────────┘    └────────┬────────┘
     │ • Rules/mapping │          │                      │
     └─────────────────┘          │                      │
                                  ▼                      │
                         ┌───────────────────┐            │
                         │ Bedrock Knowledge│◄───────────┘
                         │ Base             │
                         │                  │
                         │ legal / semantic │
                         │ retrieval        │
                         └───────────────────┘



## Results of the Seven Scenarios

The seven scenarios each introduce a different complication in regulatory import analysis. 

### Scenario 1 — Laptop from China

**Complication:** The buyer’s commercial description must be translated into the correct customs classification.

**Solution:** Semantic search identifies the most relevant NC code, after which the standard EU tariff is retrieved.

---

### Scenario 2 — Electrical cables from Morocco

**Complication:** The standard EU tariff may not apply because the EU–Morocco agreement can provide preferential treatment.

**Solution:** The system combines the NC classification with the origin country, retrieves the relevant agreement provisions, and checks whether the product is covered.

---

### Scenario 3 — LCD monitor from South Korea

**Complication:** The agreement uses an older tariff nomenclature, so the current NC code may not directly match the agreement tariff line.

**Solution:** The prototype reconciles the current classification with the agreement using tariff hierarchy and product descriptions. Historical NC mappings could later make this process more deterministic and explainable.

---

### Scenario 4 — Pulse oximeter from China

**Complication:** The product may be subject to medical-device requirements in addition to customs duties.

**Solution:** Customs classification and medical regulatory requirements are retrieved separately. Quantifiable customs costs are distinguished from compliance obligations whose financial impact is not available in the corpus.

---

### Scenario 5 — Hip prosthesis from India

**Complication:** This combines specialized product classification with medical-device regulation, while no India-specific agreement is available in the corpus.

**Solution:** The system applies standard tariff treatment and retrieves the relevant medical regulatory information without introducing unsupported preferential treatment.

---

### Scenario 6 — Olive oil from Tunisia

**Complication:** Agricultural tariffs may depend on quantity, weight, quotas, or other information not provided by the buyer.

**Solution:** The system identifies the relevant tariff but avoids producing a calculation when the required input data is missing.

---

### Scenario 7 — EV lithium-ion battery from China

**Complication:** The buyer’s technical wording may differ significantly from customs terminology.

**Solution:** Semantic search compares the meaning of the product description with NC descriptions and hierarchy to identify the most appropriate classification.
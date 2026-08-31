# Regulatory Engine

EU import tariff and regulatory search engine using PostgreSQL/pgvector, AWS Bedrock, AWS Textract, and Streamlit.

## Local setup

### Prerequisites

- Docker + Docker Compose
- AWS CLI configured with credentials that can access Bedrock and Textract in `eu-west-3`

```bash
aws configure
```

### Build

```bash
docker compose build web
docker compose --profile ingestion build ingestion
```

### Start the database

```bash
docker compose up -d db
```

Check that it is healthy:

```bash
docker compose ps
```

### Ingest the regulatory corpus

NC tariff data:

```bash
docker compose --profile ingestion run --rm ingestion \
  python -m regulatory_engine.ingestion.nc.run
```

FTA data:

```bash
docker compose --profile ingestion run --rm ingestion \
  python -m regulatory_engine.ingestion.fta.run
```

### Start the application

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

## Verify the database

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

## Rebuild from scratch

This deletes the Docker PostgreSQL volume.

```bash
docker compose down -v
docker compose up -d db

docker compose --profile ingestion run --rm ingestion \
  python -m regulatory_engine.ingestion.nc.run

docker compose --profile ingestion run --rm ingestion \
  python -m regulatory_engine.ingestion.fta.run

docker compose up -d web
```

## Stop

Preserve the database:

```bash
docker compose down
```

Delete the database volume too:

```bash
docker compose down -v
```
# Cloud God Platform

**AWS/Terraform reference implementation for document intelligence and RAG workflows.**

This repository explores how a document-processing backend can be structured for AWS using FastAPI, PostgreSQL, Redis, SQS, S3, Docker, and Terraform.

## Honest status

This is a **cloud architecture reference implementation**, not a live production service. The local stack is the verified development path. The Terraform configuration describes the AWS deployment shape, but it has not been validated against sustained real-world traffic.

The current retrieval implementation is intentionally lightweight: token/TF-IDF-style scoring is used for local search, while the embedding layer is isolated so a real sentence-transformer or hosted embedding provider can be introduced without changing the API contract.

> **Implementation boundary:** the repository currently uses lightweight lexical retrieval for the local RAG path. The `EmbeddingService` generates deterministic development vectors, but uploaded chunks are not currently indexed into pgvector, and the Terraform stack does not provision PostgreSQL/Redis or an ECS worker. AWS resources described below are the infrastructure shape under development, not evidence of a live production deployment.

## Architecture

~~~
Client
  |
  v
FastAPI API
  |---- PostgreSQL  (users, documents, chunks)
  |---- Redis       (cache / rate limiting)
  |---- SQS         (async document processing)
  |                    |
  |                    v
  |                 Worker
  |                    |
  |                    v
  |                 S3 (raw documents)

Optional RAG flow:
query -> retrieval -> context assembly -> OpenAI/Ollama answer generation
~~~

## Key engineering areas

- JWT authentication with bcrypt password hashing.
- Access/refresh token handling.
- Tenant-scoped document storage.
- SQS worker flow with dead-letter support.
- S3-backed raw document storage.
- Structured logging and health/readiness endpoints.
- Prometheus-style metrics endpoint.
- Terraform-managed AWS networking, compute, IAM, queue and storage resources.

## Repository structure

~~~
app/
  api/routes/       # auth, documents, chat, health
  core/             # configuration, logging, security, middleware
  db/               # SQLAlchemy models and sessions
  services/         # parsing, storage, queues, retrieval, RAG
  workers/          # asynchronous document processing
infra/terraform/    # Terraform configuration
tests/              # unit/integration-style tests
docker-compose.yml  # local development stack
~~~

## Run locally

~~~
cp .env.example .env
docker compose up --build
~~~

API: http://localhost:8000  
Swagger: http://localhost:8000/docs

## Limitations

- Local retrieval is not a neural semantic-search implementation yet.
- The repository is not currently a live AWS deployment.
- The Terraform stack should be validated in an AWS account before operational use.
- Development database, logs, local storage, and uploaded documents must never be committed.

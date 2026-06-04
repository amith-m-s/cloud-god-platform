# Cloud God Platform

**Production-grade cloud platform on AWS. FastAPI · PostgreSQL · Redis · S3 · SQS · RAG · Terraform IaC.**

[![Python](https://img.shields.io/badge/Python_3.11-3776AB?style=flat-square&logo=python&logoColor=white)](https://github.com/amith-m-s/aws)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://github.com/amith-m-s/aws)
[![Terraform](https://img.shields.io/badge/Terraform-7B42BC?style=flat-square&logo=terraform&logoColor=white)](https://github.com/amith-m-s/aws)
[![AWS](https://img.shields.io/badge/AWS-232F3E?style=flat-square&logo=amazonaws&logoColor=white)](https://github.com/amith-m-s/aws)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

> **Note:** This repo is named `aws` for historical reasons. The platform is Cloud God — a multi-tenant document intelligence and RAG service.

---

## What This Is

A complete cloud-native backend platform. Multi-tenant document ingestion, semantic search, and RAG-based Q&A — with the full infrastructure to run it in production on AWS. Not a tutorial scaffold. Not a proof of concept. The architecture mirrors how real document intelligence services are built.

---

## System Architecture

```
                    Client
                      │
                      ▼
                 CloudFront  ──────────────────────── S3 (static assets)
                      │
                      ▼
          Application Load Balancer (ALB)
          health check: /health
                      │
                      ▼
        ┌─────────────────────────────────┐
        │     FastAPI  (ECS Fargate)      │
        │                                 │
        │  /api/v1/auth    JWT + bcrypt   │
        │  /api/v1/docs    doc pipeline   │
        │  /api/v1/chat    RAG endpoint   │
        │  /health         liveness       │
        │  /ready          readiness      │
        │  /metrics        Prometheus     │
        └────────┬──────────┬────────────┘
                 │          │           │
                 ▼          ▼           ▼
          PostgreSQL      Redis        SQS Queue
          + pgvector    (cache +       (async doc
          (documents,    idempotency    pipeline)
          embeddings,    + rate             │
          tenants)       limiting)          ▼
                                    Worker (ECS Fargate)
                                    chunk → embed → index
                                           │
                                           ▼
                                     S3 (raw docs)
```

---

## API Reference

### Authentication

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/auth/register` | Create account — bcrypt password hash |
| `POST` | `/api/v1/auth/login` | Authenticate, receive access + refresh tokens |
| `POST` | `/api/v1/auth/refresh` | Rotate refresh token |
| `GET` | `/api/v1/auth/me` | Current user profile (auth required) |

### Documents

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/documents/upload` | Upload document → queued for processing |
| `GET` | `/api/v1/documents` | List documents (paginated, tenant-scoped) |
| `POST` | `/api/v1/documents/seed` | Seed plain text directly |
| `POST` | `/api/v1/documents/search` | Semantic search across tenant knowledge base |

### RAG Chat

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/chat` | Ask question → retrieves context → generates answer |

### System

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Liveness probe — always 200 if process is alive |
| `GET` | `/ready` | Readiness probe — checks DB + Redis connectivity |
| `GET` | `/metrics` | Prometheus metrics export |

---

## Project Structure

```
cloudgod/
├── app/
│   ├── api/routes/
│   │   ├── auth.py             # Auth endpoints
│   │   ├── chat.py             # RAG chat endpoint
│   │   ├── documents.py        # Document management
│   │   └── health.py           # /health, /ready, /metrics
│   ├── core/
│   │   ├── config.py           # Pydantic Settings — env var validation
│   │   ├── logging.py          # Structured JSON logging
│   │   ├── middleware.py       # Request ID injection + access logging
│   │   └── security.py        # JWT encode/decode + bcrypt
│   ├── db/
│   │   ├── deps.py             # FastAPI dependency injection
│   │   ├── models.py           # SQLAlchemy ORM models
│   │   └── session.py          # Engine + session factory
│   ├── schemas/                # Pydantic request/response models
│   ├── services/
│   │   ├── document_service.py # Orchestrates upload → queue
│   │   ├── embedding_service.py# Text → vector
│   │   ├── queue_service.py    # SQS publish/consume
│   │   ├── rag_service.py      # Retrieval + answer generation
│   │   └── s3_service.py       # S3 upload/download
│   ├── workers/
│   │   └── processor.py        # SQS worker: chunk → embed → index
│   └── main.py
├── infra/terraform/
│   ├── main.tf                 # VPC, subnets, IGW, NAT Gateway
│   ├── ecs.tf                  # ECS cluster, task definitions, services
│   ├── alb.tf                  # ALB, target groups, listeners
│   ├── s3.tf                   # S3 bucket, versioning, AES-256, public block
│   ├── sqs.tf                  # SQS queue + DLQ (maxReceiveCount=3)
│   ├── iam.tf                  # Least-privilege roles for ECS tasks
│   ├── cloudwatch.tf           # Log groups, 14-day retention
│   └── variables.tf
├── local_storage/              # Local S3-compatible storage for dev
├── tests/
├── .env.example                # Environment variable template
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## Infrastructure (Terraform)

The `infra/terraform/` directory provisions the complete AWS stack:

```
Networking:   VPC + public/private subnets + NAT Gateway + IGW
Compute:      ECS Fargate (app + worker) with CPU/memory auto-scaling
Load Balancer:ALB with health checks on /health
Storage:      S3 — versioning on, AES-256 server-side encryption, public access blocked
Queue:        SQS standard queue + DLQ (maxReceiveCount=3)
Security:     IAM roles scoped to S3 prefix + SQS queue ARN only
Observability:CloudWatch log groups, 14-day retention
```

```bash
cd infra/terraform
terraform init
terraform plan
terraform apply
```

---

## Local Development

```bash
git clone https://github.com/amith-m-s/aws
cd aws
cp .env.example .env          # Fill in secrets

docker compose up --build     # Starts FastAPI + PostgreSQL + Redis + worker

# API:     http://localhost:8000
# Docs:    http://localhost:8000/docs
# ReDoc:   http://localhost:8000/redoc
```

---

## Testing

```bash
pip install pytest httpx
python -m pytest tests/ -v
```

Tests cover auth flows, document upload, health endpoints, and readiness checks.

---

## Production Security Decisions

| Concern | Implementation |
|---|---|
| Password storage | bcrypt — no plaintext, no MD5/SHA1 |
| Token rotation | Refresh token rotation on every `/auth/refresh` call |
| Rate limiting | Middleware-level — rejects before hitting business logic |
| Secrets | `.env` only — `.env.example` template committed, `.env` gitignored |
| S3 access | IAM role scoped to specific bucket prefix — not `s3:*` |
| SQS access | IAM role scoped to specific queue ARN |

---

## Honest Limitations

- **pgvector embeddings use TF-IDF**, not a neural embedding model. Semantic search quality is lower than sentence-transformer or OpenAI embeddings. The service layer is designed to swap this without touching API contracts.
- **RAG answer generation is basic** — context retrieval works, generation quality depends on the underlying model which is not production-grade in this scaffold.
- **Single commit history** — the project was built and pushed as a complete scaffold. Development history is not visible.
- **Not deployed live** — Terraform is ready, but the system has not been deployed to a live AWS account with real traffic. The local Docker setup runs correctly.
- **The `.db` files committed to the repo** (`cloudgod.db`, `cloudgod.db-shm`, `cloudgod.db-wal`) are SQLite development artifacts that should have been gitignored. Add them to `.gitignore` before any serious use.

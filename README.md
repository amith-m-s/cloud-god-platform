<div align="center">

# ☁️ Cloud God Platform

**Production-Grade AWS Cloud Platform — FastAPI · PostgreSQL · Redis · S3 · SQS · RAG**

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## 🏗️ Architecture

```text
                         ┌──────────────┐
                         │    Client     │
                         └──────┬───────┘
                                │
                         ┌──────▼───────┐
                         │  CloudFront  │
                         └──────┬───────┘
                                │
                    ┌───────────▼───────────┐
                    │   Application Load    │
                    │   Balancer (ALB)      │
                    └───────────┬───────────┘
                                │
              ┌─────────────────▼─────────────────┐
              │     FastAPI Service (ECS Fargate)  │
              │  ┌─────────┬─────────┬──────────┐ │
              │  │  Auth   │  Docs   │  Chat/   │ │
              │  │  Routes │  Routes │  RAG     │ │
              │  └─────────┴────┬────┴──────────┘ │
              └─────────────────┼─────────────────┘
                   │            │            │
         ┌─────────▼──┐  ┌─────▼─────┐  ┌───▼────────┐
         │ PostgreSQL  │  │   Redis   │  │    SQS     │
         │ + pgvector  │  │  (Cache)  │  │  (Queue)   │
         └─────────────┘  └───────────┘  └───┬────────┘
                                             │
                               ┌─────────────▼─────────────┐
                               │  Worker Service            │
                               │  (ECS Fargate)             │
                               │  Chunk → Embed → Index     │
                               └─────────────┬─────────────┘
                                             │
                                        ┌────▼────┐
                                        │   S3    │
                                        │ (Docs)  │
                                        └─────────┘
```

## ✨ Features

- **JWT Authentication** — Register, login, token refresh with bcrypt password hashing
- **Multi-Tenant Document Pipeline** — Upload, chunk, embed, and index documents per tenant
- **Semantic Search & RAG** — TF-IDF-based search with context-aware answer generation
- **Async Worker Pipeline** — SQS-backed background processing with retry and DLQ
- **Observability** — Structured JSON logging, Prometheus metrics, request ID tracing
- **Production Security** — Rate limiting, CORS hardening, input validation
- **Infrastructure as Code** — Complete Terraform stack for AWS deployment
- **Dockerized Development** — One-command local setup with health checks

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for local development)

### Local Development

```bash
# Clone and configure
cp .env.example .env

# Start all services
docker compose up --build

# API available at http://localhost:8000
# Swagger UI at http://localhost:8000/docs
# ReDoc at http://localhost:8000/redoc
```

### Without Docker

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## 📡 API Reference

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Create new user account |
| POST | `/api/v1/auth/login` | Authenticate and get tokens |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| GET | `/api/v1/auth/me` | Get current user profile |

### Documents

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/documents/upload` | Upload a document |
| GET | `/api/v1/documents` | List documents (paginated) |
| POST | `/api/v1/documents/seed` | Seed document text |
| POST | `/api/v1/documents/search` | Semantic search |

### RAG Chat

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/chat` | Ask questions against knowledge base |

### System

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Liveness probe |
| GET | `/ready` | Readiness probe (DB + Redis) |
| GET | `/metrics` | Prometheus metrics |

## 🧪 Testing

```bash
pip install pytest httpx
python -m pytest tests/ -v
```

## 🏭 AWS Deployment

The `infra/terraform/` directory provides a production-ready AWS stack:

- **Networking**: VPC, public/private subnets, NAT Gateway, Internet Gateway
- **Compute**: ECS Fargate with auto-scaling (CPU & memory targets)
- **Load Balancer**: ALB with health checks and HTTPS-ready listener
- **Database**: RDS PostgreSQL (provision separately)
- **Cache**: ElastiCache Redis (provision separately)
- **Storage**: S3 with versioning, AES-256 encryption, and public access block
- **Queue**: SQS with dead-letter queue (maxReceiveCount = 3)
- **Security**: IAM roles with least-privilege S3 and SQS policies
- **Observability**: CloudWatch log groups with 14-day retention

```bash
cd infra/terraform
terraform init
terraform plan
terraform apply
```

## 📁 Project Structure

```
app/
├── api/routes/          # FastAPI route handlers
│   ├── auth.py          # Authentication endpoints
│   ├── chat.py          # RAG chat endpoint
│   ├── documents.py     # Document management
│   └── health.py        # Health & metrics
├── core/                # Cross-cutting concerns
│   ├── config.py        # Pydantic settings
│   ├── logging.py       # Structured logging
│   ├── middleware.py     # Request ID & logging middleware
│   └── security.py      # JWT & password utilities
├── db/                  # Database layer
│   ├── deps.py          # FastAPI dependencies
│   ├── models.py        # SQLAlchemy models
│   └── session.py       # Engine & session factory
├── schemas/             # Pydantic request/response models
├── services/            # Business logic
│   ├── document_service.py
│   ├── embedding_service.py
│   ├── queue_service.py
│   ├── rag_service.py
│   └── s3_service.py
├── workers/             # Background processors
│   └── processor.py
└── main.py              # Application entry point
infra/terraform/         # AWS infrastructure
tests/                   # Test suite
```

## 📄 License

MIT

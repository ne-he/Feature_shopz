---
title: Feature Store MVP
emoji: ⚡
colorFrom: orange
colorTo: red
sdk: docker
app_port: 7860
pinned: false
short_description: Low-latency e-commerce ML feature store — live demo
---

# Feature Store MVP

> Production-grade feature store for e-commerce ML serving.
> Ingests transaction data, computes 20+ user-level features in batch,
> serves them via a low-latency REST API, and monitors freshness & drift.

**Status:** ✅ All milestones complete (M1–M4) — ingestion → features → serving API → monitoring.

---

## Architecture

```mermaid
flowchart TB
    subgraph Sources["📥 Data Sources"]
        CSV[ecommerce_synthetic_dataset.csv]
    end

    subgraph Ingestion["⚙️ Ingestion Layer"]
        LOAD[loader.py — CSV → DataFrame]
        CLEAN[cleaner.py — clip, parse, coerce]
    end

    subgraph Compute["🧮 Feature Computation (M2)"]
        PIPE[pipeline.py]
        RFM[rfm.py · behavior.py · temporal.py ...]
    end

    subgraph Storage["💾 Storage Layer"]
        PG[(PostgreSQL 15\nOffline Store)]
        REDIS[(Redis 7\nOnline Store)]
    end

    subgraph Serving["🌐 Serving Layer (M3)"]
        API[FastAPI — /features/online /batch]
    end

    subgraph Monitoring["📊 Monitoring (M4)"]
        DASH[Streamlit Dashboard]
        DRIFT[Evidently — Drift Detection]
    end

    CSV --> LOAD --> CLEAN --> PIPE --> RFM --> PG
    PG --> REDIS
    REDIS --> API
    PG --> DASH
    PG --> DRIFT --> DASH
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ |
| API | FastAPI + Uvicorn |
| Validation | Pydantic v2 + pydantic-settings |
| Data processing | Pandas + Polars |
| Offline store | PostgreSQL 15 (SQLAlchemy 2.0 + Alembic) |
| Online store | Redis 7 |
| Orchestration | APScheduler (daily refresh) |
| Monitoring | Streamlit + Evidently |
| Testing | pytest + pytest-cov |
| Linting | Ruff + Black + Mypy |
| Dev infra | Docker Compose |

## Prerequisites

- Python 3.11 or newer
- Docker + Docker Compose (for PostgreSQL + Redis)
- `make` (optional — wraps all common commands)

## Quick Start

```bash
# 1. Clone and enter the project
git clone <repo-url> && cd feature-store-mvp

# 2. Copy the env template and (optionally) edit credentials
cp .env.example .env

# 3. Install dependencies + pre-commit hooks
make setup          # runs: pip install -e ".[dev]" && pre-commit install

# 4. Bring up PostgreSQL + Redis
make up             # runs: docker compose up -d
# Wait ~10 s for healthchecks to pass, then:
docker compose ps   # both services should show "(healthy)"

# 5. Move the dataset into place (see "Dataset Setup" below), then seed the DB
python scripts/seed_data.py

# 6. Run the test suite
make test           # runs: pytest (with coverage)

# 7. Lint & type-check
make lint           # runs: ruff check . && mypy src/
```

## Services (Docker Compose)

| Service | Image | Default port | Purpose |
|---------|-------|-------------|---------|
| `postgres` | `postgres:15-alpine` | 5432 | Offline feature store (historical data) |
| `redis` | `redis:7-alpine` | 6379 | Online feature store (low-latency serving) |

Both services define healthchecks, use named Docker volumes
(`postgres_data`, `redis_data`), and read credentials from `.env`.

## Running the Stack

> On Windows, invoke the project venv directly: `.\.venv\Scripts\python.exe -m <cmd>`.

### Zero-infra demo (no Docker)

The fastest way to see the whole thing — API **and** the showcase frontend —
running live without PostgreSQL or Redis:

```bash
python scripts/demo_server.py     # seeds in-memory stores, serves http://localhost:8000
```

Open <http://localhost:8000>: the landing page calls the real API for the
feature catalog, a live single-user lookup (try user `12345`), and the health
badge. Every endpoint row is clickable to run it against the response panel.

### Full stack (real PostgreSQL + Redis)

```bash
# Serving API (M3) — Swagger UI at http://localhost:8000/docs, frontend at /
uvicorn src.api.main:app --reload

# Monitoring dashboard (M4) — opens at http://localhost:8501
streamlit run src/dashboard/app.py

# One-off feature refresh (compute → offline store → sync to Redis)
python -c "from src.orchestration.jobs import run_refresh_job; run_refresh_job()"

# API latency benchmark (against the running server)
python scripts/benchmark_api.py --base-url http://localhost:8000
```

The daily refresh is scheduled with APScheduler (`src/orchestration/flows.py`,
`build_scheduler()`); see the [runbook](docs/runbook.md) for operating it.

### API Endpoints (M3)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Liveness + Postgres/Redis probes |
| `GET` | `/features/online/{user_id}` | Redis-first lookup, Postgres fallback |
| `POST` | `/features/batch` | Up to 100 users in one call |
| `GET` | `/features/offline/{user_id}` | Postgres-only (training lookups) |
| `GET` | `/features/metadata` | Feature catalog from the registry |

## Dataset Setup

This project uses the **E-Commerce Synthetic Dataset** (100k rows × 21 columns,
synthetic, CC0 Public Domain). The file is **not committed to git**.

The CSV (`ecommerce_synthetic_dataset.csv`) currently lives in the project root.
Move it into place before running `seed_data.py`:

```bash
# bash / git-bash
mv ecommerce_synthetic_dataset.csv data/raw/ecommerce_synthetic_dataset.csv
```

```powershell
# PowerShell
Move-Item ecommerce_synthetic_dataset.csv data\raw\ecommerce_synthetic_dataset.csv
```

More details: [`data/README.md`](data/README.md).

## Project Structure

```
src/
  config.py            Pydantic Settings — reads .env
  ingestion/           loader, schema, cleaner
  features/            RFM, behavior, engagement, temporal, discount, demographics (M2)
  storage/             SQLAlchemy models, offline (PG) + online (Redis) stores (M2-M3)
  api/                 FastAPI app + routes (M3)
  orchestration/       APScheduler daily refresh job (M4)
  monitoring/          Freshness, Evidently drift, store metrics (M4)
  dashboard/           Streamlit app — 4 pages (M4)

tests/
  conftest.py          Shared fixtures
  unit/                Pure function tests (no DB needed)
  integration/         End-to-end tests (requires Docker services)
  fixtures/            10-row sample CSV

scripts/
  seed_data.py         DB init + ingestion validation
  recompute_features.py  Manual feature recompute trigger (M2)
  benchmark_api.py     Latency load test (M3)

alembic/              Alembic migrations (initial schema in versions/001)
docs/                 Architecture, API spec, feature catalog, runbook
```

## Milestones

| # | Milestone | Status |
|---|-----------|--------|
| **M1** | Foundation & Data Layer | ✅ Done |
| **M2** | Feature Computation Engine (23 features) | ✅ Done |
| **M3** | Serving Layer (FastAPI + Redis) | ✅ Done |
| **M4** | Monitoring, Drift & Dashboard | ✅ Done |

Target API latency: p99 < 100 ms single / < 500 ms batch-100.
In-process benchmark (no network hop): single p99 ≈ 22 ms, batch-100 p99 ≈ 79 ms.
Run `python scripts/benchmark_api.py --base-url http://localhost:8000` for real-stack numbers.

## Testing

```bash
pytest                         # all tests + coverage report
pytest tests/unit/ -v          # unit tests only (no Docker needed)
ruff check . && mypy src/      # lint + type-check
```

Module coverage targets (per `PRD.md § 16`):

| Module | Target | Current |
|--------|--------|---------|
| `src/ingestion/` | ≥ 85% | ✅ |
| `src/features/` | ≥ 90% | ✅ |
| `src/storage/` | ≥ 80% | ✅ |
| `src/api/` | ≥ 80% | ✅ |
| `src/monitoring/` | ≥ 80% | ✅ |
| Overall | ≥ 80% | **95%** (174 tests) |

## Database Migrations

Alembic is configured to read credentials from `.env` via `src/config.settings`:

```bash
# Apply all migrations (requires `make up` first)
alembic upgrade head

# Roll back one step
alembic downgrade -1

# Generate a new migration after changing ORM models
alembic revision --autogenerate -m "describe change"
```

## License

MIT — see `pyproject.toml`.

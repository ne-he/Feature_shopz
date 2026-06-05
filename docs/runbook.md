# Runbook — Feature Store MVP

Operational playbook for running and troubleshooting the feature store
locally. Covers the daily refresh, the serving API, the monitoring dashboard,
and the most common failure modes.

> On Windows, run commands through the project venv:
> `.\.venv\Scripts\python.exe -m <cmd>`.

---

## 1. Daily Operations

### Bring the stack up
```bash
docker compose up -d          # PostgreSQL + Redis
docker compose ps             # both should be "(healthy)"
alembic upgrade head          # apply migrations (first run only)
```

### Refresh features (compute → offline → online)
```bash
python -c "from src.orchestration.jobs import run_refresh_job; run_refresh_job()"
```
Returns `{rows_written, rows_synced, duration_sec}`. The scheduled equivalent
runs every `FEATURE_REFRESH_CADENCE_HOURS` (default 24) via APScheduler
(`src/orchestration/flows.py::build_scheduler`).

### Serve features
```bash
uvicorn src.api.main:app          # http://localhost:8000/docs
```

### Monitor
```bash
streamlit run src/dashboard/app.py   # http://localhost:8501
```

---

## 2. Health & Verification

| Check | Command | Healthy result |
|-------|---------|----------------|
| API + stores | `curl localhost:8000/health` | `status: healthy`, both checks `ok` |
| Feature freshness | Dashboard → Overview | 🟢 fresh (age < cadence) |
| Test suite | `pytest -q` | all pass, coverage ≥ 80% |
| Lint / types | `ruff check . && mypy src/` | clean |

---

## 3. Drift Detection

1. After a known-good refresh, save the current distribution as the baseline:
   ```python
   from sqlalchemy import create_engine
   from src.config import settings
   from src.monitoring.drift import save_baseline
   from src.monitoring.metrics import load_feature_frame
   eng = create_engine(settings.postgres_url)
   save_baseline(load_feature_frame(eng))   # -> data/processed/feature_baseline.parquet
   ```
2. The dashboard **Drift** page compares the latest features against that
   baseline (Evidently `DataDriftPreset`). Persist verdicts with
   `persist_drift_metrics(engine, results)` → `drift_metrics` table.
3. Per-feature rule: K-S `p_value < threshold` (default 0.05) ⇒ drift.

---

## 4. Troubleshooting

### `/health` returns 503
- **`postgres: unavailable`** — is the container up? `docker compose ps`.
  Check `.env` credentials match `docker-compose.yml`. Try `alembic upgrade head`.
- **`redis: unavailable`** — `docker compose restart redis`; confirm port 6379.

### API returns 404 for a known user
Features have not been synced to Redis (or expired past the 25h TTL). Re-run
the refresh job; the online endpoint also falls back to Postgres automatically.

### Online lookups are slow / stale
- Stale: check the dashboard **Overview** freshness; re-run the refresh job.
- Slow: confirm Redis is reachable (lookups fall back to Postgres on a miss,
  which is slower). Benchmark with `scripts/benchmark_api.py --base-url ...`.

### Tests fail with `ModuleNotFoundError`
You are using the wrong interpreter. Always run via the project venv
(`.\.venv\Scripts\python.exe -m pytest`), **not** the global `python`/`pip`.

### Drift page says "No baseline saved"
Run the baseline-save snippet in §3 first.

---

## 5. Data Recovery

PostgreSQL data persists in the `postgres_data` Docker volume. Back up / restore:
```bash
docker compose exec postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > backup.sql
docker compose exec -T postgres psql -U "$POSTGRES_USER" "$POSTGRES_DB" < backup.sql
```
Redis is a cache and is rebuilt from Postgres on the next refresh — no backup
needed.

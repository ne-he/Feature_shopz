# Deploying the Feature Store MVP to Render (public)

This guide takes the API **and** the MLv2 showcase frontend live on
[Render](https://render.com) using the free tier. It provisions three managed
resources from `render.yaml`:

| Resource | Type | Role |
|----------|------|------|
| `feature-store-api` | Docker web service | FastAPI + serves the frontend at `/` |
| `feature-store-db` | PostgreSQL 15 | Offline store |
| `feature-store-cache` | Key Value (Redis) | Online store (internal-only) |

> **Scope:** API + frontend only. The Streamlit dashboard stays local.
> **Cost:** $0 on the free tier (see [Gotchas](#gotchas-free-tier-realities)).

---

## How serving works (why seeding is easy)

`GET /features/online/{user_id}` is **Redis-first with a PostgreSQL fallback**
(`src/api/routes/features.py`). So:

- Seed **Postgres only** → single-user lookups already work (served from the
  PG fallback). **This is enough for a live demo** — the frontend's hero
  lookup (user `12345`) will return real features.
- Sync **Redis** afterwards → the `/features/batch` endpoint works and single
  lookups are served from Redis (lower latency, `source: "redis"`).

---

## Prerequisites

- A Render account (sign up with GitHub).
- The repo pushed to GitHub — already at `ne-he/Feature_shopz`.
- The dataset present locally at `data/raw/ecommerce_synthetic_dataset.csv`
  (used only for seeding from your laptop; it is never shipped in the image).

---

## Step 1 — Push the deploy files

These files drive the deploy and must be on the branch Render builds:

- `Dockerfile`, `.dockerignore`
- `render.yaml`
- `src/config.py` (now reads `DATABASE_URL` / `REDIS_URL`)

```powershell
git add Dockerfile .dockerignore render.yaml src/config.py docs/deploy_render.md
git commit -m "feat(deploy): containerize API + Render blueprint for public deploy"
git push origin master
```

## Step 2 — Create the Blueprint on Render

1. Render Dashboard → **New +** → **Blueprint**.
2. Connect the `ne-he/Feature_shopz` repo. Render detects `render.yaml` and
   lists the 3 resources.
3. Click **Apply**. First build takes **~5–10 min** (the image installs
   pandas/polars/etc.).
4. When the web service is **Live**:
   - `https://feature-store-api.onrender.com/health` → `200` `{"status":"healthy"}`
     (both stores reachable, just empty).
   - `/` loads the frontend; `/docs` shows Swagger.
   - A lookup like `/features/online/12345` returns **404** for now — no data
     yet. That's expected; seed next.

> Your exact URL is shown in the service header; it may differ from the example
> above if the name was taken.

## Step 3 — Seed the offline store (from your laptop)

The dataset lives on your machine, so compute features locally and write them
straight into the **cloud Postgres**.

1. In Render → `feature-store-db` → copy the **External Connection String**
   (looks like `postgresql://USER:PASS@HOST.oregon-postgres.render.com/DB`).
2. From the project root, point `DATABASE_URL` at it and run the compute+write:

```powershell
$env:DATABASE_URL = "postgresql://USER:PASS@HOST.oregon-postgres.render.com/DB"
.\.venv\Scripts\python.exe -c "from pathlib import Path; from sqlalchemy import create_engine; from src.config import settings; from src.features.pipeline import run_feature_pipeline; from src.storage.offline_store import write_features_to_db; e=create_engine(settings.postgres_url); f=run_feature_pipeline(Path('data/raw/ecommerce_synthetic_dataset.csv')); print(write_features_to_db(f, e)); e.dispose()"
Remove-Item Env:\DATABASE_URL
```

3. Verify against the live API:
   `https://feature-store-api.onrender.com/features/online/12345` → **200**
   with features and `"source": "postgres"`. 🎉 The demo is now live.

> The migration (`alembic upgrade head`) already created the tables on first
> boot, so this just fills them.

## Step 4 — Sync Redis (optional, enables `/batch` + the fast path)

Run this **inside Render** so it uses the internal Redis (no TLS/IP setup). The
dataset is not needed — it reads the already-seeded Postgres.

1. Render → `feature-store-api` → **Shell** tab.
2. Run:

```bash
python -c "from sqlalchemy import create_engine; from src.config import settings; from src.storage.online_store import get_redis_client; from src.storage.sync import sync_offline_to_online; print(sync_offline_to_online(create_engine(settings.postgres_url), get_redis_client()))"
```

3. Re-check `/features/online/12345` → now `"source": "redis"`, and
   `POST /features/batch` returns data.

> Free Redis is internal-only (`ipAllowList: []`), so this sync must run from
> the Render Shell, not your laptop. The 25-hour TTL means Redis empties if not
> refreshed; re-run this (or wire APScheduler) to keep it warm.

---

## Gotchas (free-tier realities)

- **Cold starts:** the free web service spins down after ~15 min idle; the next
  request takes ~50 s to wake. Fine for a portfolio demo.
- **Postgres expires:** free Render Postgres is deleted after **90 days**.
  Re-create + re-seed, or upgrade to keep it permanent.
- **Slow first build:** the image bundles Streamlit/Evidently (unused by the
  API). To speed builds, add an `api` extra in `pyproject.toml` and switch the
  Dockerfile to `pip install ".[api]"`.
- **SSL:** psycopg2's default (`sslmode=prefer`) negotiates TLS with Render's
  external Postgres automatically, so the seed step needs no extra flags.
- **Migrations on every start:** runs in the container `CMD`; it's a no-op once
  at head. On a paid plan, move it to `render.yaml`'s `preDeployCommand`.

## Rollback / teardown

Delete the Blueprint (or each resource) from the Render Dashboard. Nothing runs
locally is affected; this repo's local Docker workflow is unchanged.

# syntax=docker/dockerfile:1
#
# Production image for the Feature Store API (FastAPI + the served MLv2 frontend).
#
# Single stage on python:3.11-slim. psycopg2-binary bundles its own libpq and
# every runtime dependency ships a manylinux wheel, so no compiler or apt
# packages are required.
#
# For simplicity this installs ALL runtime deps — including Streamlit/Evidently,
# which only the dashboard uses. The API process never imports those, so they
# cost build time + image size but not runtime RAM. To slim the image later,
# add an `api` optional-dependency group in pyproject.toml and switch the
# install line to `pip install ".[api]"`.

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Packaging metadata + source needed to build and install the `src` package.
# Only the MLv2 frontend is copied (it is the one served at "/").
COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY frontend/MLv2/ ./frontend/MLv2/

RUN pip install .

# Run as an unprivileged user.
RUN useradd --create-home --uid 10001 appuser && chown -R appuser /app
USER appuser

# Render injects $PORT at runtime; default to 8000 for a plain `docker run`.
EXPOSE 8000

# Apply migrations (idempotent: a no-op when already at head) then serve.
# On a paid Render plan you can move the migration to render.yaml's
# preDeployCommand instead of running it on every start.
CMD ["sh", "-c", "alembic upgrade head && uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

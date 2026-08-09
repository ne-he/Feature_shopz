# Hugging Face Spaces: live demo image.
#
# Runs the zero-infra demo server (scripts/demo_server.py): the real FastAPI app
# + MLv2 frontend, backed by an in-memory SQLite offline store and a fakeredis
# online store seeded with 201 sample users. No external Postgres/Redis needed.
#
# HF Spaces routes public traffic to $PORT (7860); the demo server reads HOST
# and PORT from the environment (set below).

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HOST=0.0.0.0 \
    PORT=7860

WORKDIR /app

# Packaging metadata + source + the served frontend + the demo entrypoint.
COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY frontend/MLv2/ ./frontend/MLv2/

# Serving-only dependency set, installed explicitly rather than via `pip install .`.
#
# pyproject's `dependencies` list covers the whole project, including the
# Streamlit dashboard (streamlit, plotly) and the drift monitor (evidently, which
# drags scipy + scikit-learn + statsmodels). This image only ever runs
# scripts/demo_server.py, whose import chain is demo_server -> src.api.main ->
# src.api.routes / src.config / src.features / src.storage. That chain imports
# none of those packages, and polars is not imported anywhere in src/ at all.
# Installing the full set cost roughly 1 GB of site-packages, of which about
# 850 MB was never loaded at runtime: pure image size and cold-start time.
#
# psycopg2-binary IS required despite the demo using SQLite. The app lifespan in
# src/api/main.py calls create_engine(settings.postgres_url), and SQLAlchemy
# imports the DBAPI driver when the engine is constructed. The engine is then
# replaced by demo_server's dependency override and never connects, but the
# import must still succeed or startup fails.
#
# `--no-deps` on the project install keeps pip from pulling the full pyproject
# set back in. It prints a harmless consistency warning for the omitted extras.
RUN pip install \
        "fastapi>=0.110.0" \
        "uvicorn[standard]>=0.27.0" \
        "pydantic>=2.5.0" \
        "pydantic-settings>=2.0.0" \
        "sqlalchemy>=2.0.0" \
        "psycopg2-binary>=2.9.0" \
        "pandas>=2.1.0" \
        "redis>=5.0.0" \
        "loguru>=0.7.0" \
        "python-dotenv>=1.0.0" \
        "fakeredis>=2.20.0" \
 && pip install --no-deps .

# Run as the non-root user Hugging Face expects (UID 1000).
RUN useradd -m -u 1000 user && chown -R user /app
USER user

EXPOSE 7860

CMD ["python", "scripts/demo_server.py"]

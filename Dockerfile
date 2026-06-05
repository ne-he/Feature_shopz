# Hugging Face Spaces — live demo image.
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

# Runtime deps (from pyproject) + fakeredis, the demo's in-memory Redis stand-in.
RUN pip install . fakeredis

# Run as the non-root user Hugging Face expects (UID 1000).
RUN useradd -m -u 1000 user && chown -R user /app
USER user

EXPOSE 7860

CMD ["python", "scripts/demo_server.py"]

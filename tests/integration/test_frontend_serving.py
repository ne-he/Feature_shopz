"""Integration tests for the static frontend mount and CORS (M5).

These need no database or Redis: serving the showcase page and answering a
CORS preflight are handled before any store is touched.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from src.api.dependencies import get_engine
from src.api.main import create_app


def test_root_serves_frontend_index() -> None:
    """GET / returns the static showcase HTML, not an API route."""
    with TestClient(create_app()) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Feature Store" in resp.text


def test_api_routes_take_precedence_over_static_mount(offline_engine: Engine) -> None:
    """The static mount at '/' must not shadow the API routes or docs."""
    app = create_app()
    app.dependency_overrides[get_engine] = lambda: offline_engine
    with TestClient(app) as client:
        assert client.get("/openapi.json").status_code == 200
        resp = client.get("/features/metadata")
    assert resp.status_code == 200
    assert "application/json" in resp.headers["content-type"]
    assert "features" in resp.json()


def test_cors_preflight_allows_cross_origin() -> None:
    """An OPTIONS preflight returns the permissive CORS header."""
    with TestClient(create_app()) as client:
        resp = client.options(
            "/features/metadata",
            headers={
                "Origin": "http://localhost:5500",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert resp.headers.get("access-control-allow-origin") == "*"

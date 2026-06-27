"""Tests del API. Sin DB real: el pool se mockea y los services se parchean.

Cada endpoint debe responder 200 (o el error esperado) con el shape correcto.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api import main


@pytest.fixture
def client():
    """TestClient con el ciclo de vida (lifespan) del pool mockeado."""
    with (
        patch("src.api.main.init_pool"),
        patch("src.api.main.close_pool"),
    ):
        with TestClient(main.app) as c:
            yield c


# --- meta -----------------------------------------------------------------------

def test_root(client):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Latam Economic Pulse API"
    assert body["docs"] == "/docs"


def test_health_connected(client):
    with patch("src.api.main.ping", return_value=True):
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "database": "connected"}


def test_health_disconnected(client):
    with patch("src.api.main.ping", side_effect=Exception("down")):
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["database"] == "disconnected"


# --- catálogos ------------------------------------------------------------------

def test_list_indicators(client):
    rows = [
        {
            "indicator_code": "NY.GDP.MKTP.CD",
            "indicator_name": "GDP (current US$)",
            "unit": "US$ corrientes",
            "category": "Cuentas nacionales",
            "description_es": "PIB...",
        }
    ]
    with patch("src.api.routers.indicators.services.list_indicators", return_value=rows):
        resp = client.get("/indicators")
    assert resp.status_code == 200
    assert resp.json()[0]["indicator_code"] == "NY.GDP.MKTP.CD"


def test_list_countries(client):
    rows = [
        {
            "country_iso3": "BOL",
            "country_name": "Bolivia",
            "iso2": "BO",
            "region": "Latin America & Caribbean",
            "income_level": "Lower middle income",
            "capital": "La Paz",
            "longitude": -66.19,
            "latitude": -13.99,
        }
    ]
    with patch("src.api.routers.indicators.services.list_countries", return_value=rows):
        resp = client.get("/countries")
    assert resp.status_code == 200
    assert resp.json()[0]["country_iso3"] == "BOL"


# --- series ---------------------------------------------------------------------

def test_country_series_ok(client):
    rows = [
        {"country_iso3": "BOL", "indicator_code": "NY.GDP.MKTP.CD", "anio": 2023, "valor": 1.0}
    ]
    with patch(
        "src.api.routers.indicators.services.get_country_series", return_value=rows
    ):
        resp = client.get("/indicators/BOL")
    assert resp.status_code == 200
    assert resp.json()[0]["anio"] == 2023


def test_country_series_not_found(client):
    with patch(
        "src.api.routers.indicators.services.get_country_series", return_value=[]
    ):
        resp = client.get("/indicators/XXX")
    assert resp.status_code == 404


def test_country_indicator_series_ok(client):
    rows = [
        {"country_iso3": "PER", "indicator_code": "FP.CPI.TOTL.ZG", "anio": 2023, "valor": 3.2}
    ]
    with patch(
        "src.api.routers.indicators.services.get_country_indicator_series",
        return_value=rows,
    ):
        resp = client.get("/indicators/PER/FP.CPI.TOTL.ZG")
    assert resp.status_code == 200
    assert resp.json()[0]["indicator_code"] == "FP.CPI.TOTL.ZG"


# --- latest / compare -----------------------------------------------------------

def test_latest_ok(client):
    rows = [
        {"country_iso3": "PER", "indicator_code": "FP.CPI.TOTL.ZG", "anio": 2023, "valor": 3.2}
    ]
    with patch(
        "src.api.routers.indicators.services.get_latest_by_indicator", return_value=rows
    ):
        resp = client.get("/latest", params={"indicator": "FP.CPI.TOTL.ZG"})
    assert resp.status_code == 200
    assert resp.json()[0]["country_iso3"] == "PER"


def test_latest_requires_indicator_param(client):
    resp = client.get("/latest")
    assert resp.status_code == 422  # falta query param obligatorio


def test_compare_ok(client):
    rows = [
        {"country_iso3": "BOL", "indicator_code": "NY.GDP.MKTP.CD", "anio": 2023, "valor": 1.0},
        {"country_iso3": "PER", "indicator_code": "NY.GDP.MKTP.CD", "anio": 2023, "valor": 2.0},
    ]
    with patch(
        "src.api.routers.indicators.services.compare_countries", return_value=rows
    ) as mock_compare:
        resp = client.get(
            "/compare", params={"countries": "BOL;PER", "indicator": "NY.GDP.MKTP.CD"}
        )
    assert resp.status_code == 200
    assert len(resp.json()) == 2
    # El router parsea los ISO3 separados por ';'.
    mock_compare.assert_called_once_with(["BOL", "PER"], "NY.GDP.MKTP.CD")


# --- stats ----------------------------------------------------------------------

def test_stats_ok(client):
    stats = {
        "indicator_code": "NY.GDP.MKTP.CD",
        "anio": 2023,
        "count": 33,
        "min_valor": 1.0,
        "max_valor": 9.0,
        "avg_valor": 5.0,
    }
    with patch("src.api.routers.stats.services.get_indicator_stats", return_value=stats):
        resp = client.get("/stats/NY.GDP.MKTP.CD")
    assert resp.status_code == 200
    assert resp.json()["count"] == 33


def test_stats_not_found(client):
    with patch("src.api.routers.stats.services.get_indicator_stats", return_value=None):
        resp = client.get("/stats/UNKNOWN")
    assert resp.status_code == 404

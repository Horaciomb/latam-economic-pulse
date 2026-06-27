"""Tests de la capa de carga. Sin DB real: conexión psycopg2 mockeada.

Verifica el UPSERT idempotente: que la sentencia use ``ON CONFLICT``, que se
pasen los valores correctos y que `execute_values` se invoque una vez por lote.
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from src.el.load import upsert_countries, upsert_observations
from src.models.schemas import WBCountry, WBObservation


def _mock_conn():
    """Conexión mock cuyo ``.cursor()`` es un context manager con un cursor mock."""
    conn = MagicMock()
    cursor = MagicMock()

    @contextmanager
    def _cursor():
        yield cursor

    conn.cursor.side_effect = _cursor
    return conn, cursor


OBS = [
    WBObservation(
        country_iso3="BOL",
        country_name="Bolivia",
        indicator_code="NY.GDP.MKTP.CD",
        indicator_name="GDP (current US$)",
        anio=2023,
        valor=52340206946.45,
    ),
    WBObservation(
        country_iso3="VEN",
        country_name="Venezuela",
        indicator_code="FP.CPI.TOTL.ZG",
        indicator_name="Inflation",
        anio=2023,
        valor=None,
    ),
]

COUNTRIES = [
    WBCountry(
        country_iso3="BOL",
        iso2="BO",
        name="Bolivia",
        region="Latin America & Caribbean",
        income_level="Lower middle income",
        capital="La Paz",
        longitude=-66.1936,
        latitude=-13.9908,
    )
]


# --- upsert_observations --------------------------------------------------------

@patch("src.el.load.execute_values")
def test_upsert_observations_is_idempotent(mock_execute_values):
    """La sentencia incluye ON CONFLICT sobre la clave natural."""
    conn, cursor = _mock_conn()

    count = upsert_observations(conn, OBS)

    assert count == 2
    mock_execute_values.assert_called_once()
    sql, values = mock_execute_values.call_args.args[1], mock_execute_values.call_args.args[2]
    assert "ON CONFLICT (country_iso3, indicator_code, anio) DO UPDATE" in sql
    assert len(values) == 2


@patch("src.el.load.execute_values")
def test_upsert_observations_maps_columns_in_order(mock_execute_values):
    """Cada tupla respeta el orden de columnas del INSERT."""
    conn, _ = _mock_conn()

    upsert_observations(conn, OBS)

    values = mock_execute_values.call_args.args[2]
    # (country_iso3, country_name, indicator_code, indicator_name, anio, valor)
    assert values[0] == (
        "BOL", "Bolivia", "NY.GDP.MKTP.CD", "GDP (current US$)", 2023, 52340206946.45,
    )
    # El valor nulo se carga tal cual (el filtrado es de dbt).
    assert values[1][-1] is None


@patch("src.el.load.execute_values")
def test_upsert_observations_empty_is_noop(mock_execute_values):
    """Lista vacía no toca la base ni invoca execute_values."""
    conn, _ = _mock_conn()

    count = upsert_observations(conn, [])

    assert count == 0
    mock_execute_values.assert_not_called()


# --- upsert_countries -----------------------------------------------------------

@patch("src.el.load.execute_values")
def test_upsert_countries_is_idempotent(mock_execute_values):
    """La sentencia de países usa ON CONFLICT sobre el ISO3."""
    conn, _ = _mock_conn()

    count = upsert_countries(conn, COUNTRIES)

    assert count == 1
    sql = mock_execute_values.call_args.args[1]
    assert "ON CONFLICT (country_iso3) DO UPDATE" in sql


@patch("src.el.load.execute_values")
def test_upsert_countries_empty_is_noop(mock_execute_values):
    """Lista vacía no invoca execute_values."""
    conn, _ = _mock_conn()

    assert upsert_countries(conn, []) == 0
    mock_execute_values.assert_not_called()

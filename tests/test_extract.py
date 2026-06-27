"""Tests de la capa de extracción. Sin red real: ``requests.Session`` mockeada.

Cubre lo crítico del shape de la World Bank API:
  * El array de 2 elementos ``[metadata, [datos]]``.
  * La paginación (iterar hasta ``page == pages``).
  * Los reintentos con backoff ante errores transitorios.
  * El segundo elemento ``None`` (respuesta sin datos).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import requests

from src.el import extract
from src.el.extract import (
    WorldBankAPIError,
    fetch_lcn_countries,
    fetch_observations,
)


def _make_response(json_body, status_code=200):
    """Construye una respuesta falsa de ``requests`` con el JSON dado."""
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.json.return_value = json_body
    resp.raise_for_status.return_value = None
    return resp


def _session_returning(*responses):
    """Sesión mock cuyo ``.get`` devuelve las respuestas dadas, en orden."""
    session = MagicMock(spec=requests.Session)
    session.get.side_effect = list(responses)
    return session


# --- Fixtures de datos crudos (shape real confirmado con curl) ------------------

COUNTRY_PAGE = [
    {"page": 1, "pages": 1, "per_page": "300", "total": 2},
    [
        {
            "id": "BOL",
            "iso2Code": "BO",
            "name": "Bolivia",
            "region": {"id": "LCN", "value": "Latin America & Caribbean "},
            "incomeLevel": {"id": "LMC", "value": "Lower middle income"},
            "capitalCity": "La Paz",
            "longitude": "-66.1936",
            "latitude": "-13.9908",
        },
        {
            "id": "LCN",
            "iso2Code": "ZJ",
            "name": "Latin America & Caribbean",
            "region": {"id": "", "value": "Aggregates"},
            "incomeLevel": {"id": "NA", "value": "Aggregates"},
            "capitalCity": "",
            "longitude": "",
            "latitude": "",
        },
    ],
]


def _obs(iso3, date, value):
    return {
        "indicator": {"id": "NY.GDP.MKTP.CD", "value": "GDP (current US$)"},
        "country": {"id": iso3[:2], "value": iso3},
        "countryiso3code": iso3,
        "date": date,
        "value": value,
        "unit": "",
        "obs_status": "",
        "decimal": 0,
    }


# --- fetch_lcn_countries --------------------------------------------------------

def test_fetch_lcn_countries_filters_aggregates_and_trims():
    """Excluye agregados y normaliza la región (espacio final)."""
    session = _session_returning(_make_response(COUNTRY_PAGE))

    countries = fetch_lcn_countries(session=session)

    assert len(countries) == 1
    bol = countries[0]
    assert bol.country_iso3 == "BOL"
    assert bol.region == "Latin America & Caribbean"  # sin espacio final
    assert bol.longitude == pytest.approx(-66.1936)


def test_fetch_lcn_countries_uses_region_filter():
    """Llama al endpoint /country con region=LCN."""
    session = _session_returning(_make_response(COUNTRY_PAGE))

    fetch_lcn_countries(session=session)

    _args, kwargs = session.get.call_args
    assert kwargs["params"]["region"] == "LCN"


# --- fetch_observations: array de 2 elementos y paginación ----------------------

def test_fetch_observations_single_page():
    """Desempaca correctamente el array de 2 elementos en una sola página."""
    page = [
        {"page": 1, "pages": 1, "per_page": 1000, "total": 2},
        [_obs("BOL", "2023", 52340206946.45), _obs("PER", "2023", 266958720837.99)],
    ]
    session = _session_returning(_make_response(page))

    observations = fetch_observations(["BOL", "PER"], session=session)

    assert len(observations) == 2
    assert {o.country_iso3 for o in observations} == {"BOL", "PER"}
    assert session.get.call_count == 1


def test_fetch_observations_paginates_until_last_page():
    """Itera páginas hasta page == pages y concatena resultados."""
    page1 = [
        {"page": 1, "pages": 2, "per_page": 1, "total": 2},
        [_obs("BOL", "2023", 1.0)],
    ]
    page2 = [
        {"page": 2, "pages": 2, "per_page": 1, "total": 2},
        [_obs("BOL", "2022", 2.0)],
    ]
    session = _session_returning(_make_response(page1), _make_response(page2))

    observations = fetch_observations(["BOL"], session=session)

    assert len(observations) == 2
    assert session.get.call_count == 2
    # La segunda llamada pide page=2.
    _args, kwargs = session.get.call_args_list[1]
    assert kwargs["params"]["page"] == 2


def test_fetch_observations_keeps_null_values():
    """Los valores nulos se conservan (el filtrado es trabajo de dbt)."""
    page = [
        {"page": 1, "pages": 1, "per_page": 1000, "total": 1},
        [_obs("VEN", "2023", None)],
    ]
    session = _session_returning(_make_response(page))

    observations = fetch_observations(["VEN"], session=session)

    assert len(observations) == 1
    assert observations[0].valor is None


def test_fetch_observations_handles_null_data_element():
    """El segundo elemento del array puede ser None (sin datos)."""
    page = [{"page": 1, "pages": 1, "per_page": 1000, "total": 0}, None]
    session = _session_returning(_make_response(page))

    observations = fetch_observations(["ATG"], session=session)

    assert observations == []


# --- Reintentos / backoff -------------------------------------------------------

def test_retry_then_success(monkeypatch):
    """Reintenta ante 503 transitorios y termina devolviendo el 200."""
    sleeps: list[float] = []
    monkeypatch.setattr(extract.time, "sleep", lambda s: sleeps.append(s))

    page = [{"page": 1, "pages": 1, "per_page": 1000, "total": 1}, [_obs("BOL", "2023", 1.0)]]
    session = _session_returning(
        _make_response(None, status_code=503),
        _make_response(None, status_code=503),
        _make_response(page, status_code=200),
    )

    observations = fetch_observations(["BOL"], session=session)

    assert len(observations) == 1
    assert session.get.call_count == 3
    # Backoff exponencial: 0.5, luego 1.0.
    assert sleeps == [0.5, 1.0]


def test_retry_exhausted_raises(monkeypatch):
    """Tras agotar los 3 intentos lanza WorldBankAPIError."""
    monkeypatch.setattr(extract.time, "sleep", lambda s: None)
    session = _session_returning(
        _make_response(None, status_code=503),
        _make_response(None, status_code=503),
        _make_response(None, status_code=503),
    )

    with pytest.raises(WorldBankAPIError):
        fetch_lcn_countries(session=session)

    assert session.get.call_count == 3


def test_unexpected_shape_raises():
    """Si la API devuelve un dict de error en vez del array de 2, falla claro."""
    session = _session_returning(_make_response({"message": "invalid"}))

    with pytest.raises(WorldBankAPIError):
        fetch_lcn_countries(session=session)

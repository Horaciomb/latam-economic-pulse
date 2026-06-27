"""Extracción desde la World Bank Indicators API v2 (capa E del EL).

Esta capa SÓLO extrae. No limpia ni transforma datos de negocio (eso es dbt) y no
toca la base de datos (eso es ``load.py``). Toda la red está aislada tras
``_request_with_retry`` para que los tests puedan mockearla sin tráfico real.

Hechos del shape de la API (confirmados con curl real):
  * Toda respuesta es un array de DOS elementos: ``[metadata, [datos]]``.
  * ``metadata`` trae ``page``, ``pages``, ``per_page`` y ``total``.
  * El segundo elemento puede ser ``None`` cuando no hay datos.
  * El filtro ``region=LCN`` ya excluye agregados; igual hay guarda defensiva.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

from src.models.schemas import WBCountry, WBObservation, WBPageMeta

logger = logging.getLogger(__name__)

BASE_URL = "https://api.worldbank.org/v2"

# Indicadores por defecto (código → significado en CLAUDE.md).
DEFAULT_INDICATORS: tuple[str, ...] = (
    "NY.GDP.MKTP.CD",  # PIB (US$ corrientes)
    "FP.CPI.TOTL.ZG",  # Inflación (% anual)
    "SL.UEM.TOTL.ZS",  # Desempleo (% fuerza laboral)
    "NY.GDP.PCAP.CD",  # PIB per cápita (US$ corrientes)
)

DEFAULT_DATE_RANGE = "2010:2024"

# Cuántos países ISO3 agrupar por request (la URL se separa con ';').
_COUNTRY_CHUNK = 30

# Reintentos.
_MAX_RETRIES = 3
_BACKOFF_BASE = 0.5  # segundos; backoff exponencial: 0.5, 1.0, 2.0...
_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})


class WorldBankAPIError(RuntimeError):
    """La World Bank API falló tras agotar los reintentos."""


def _request_with_retry(
    session: requests.Session,
    url: str,
    params: dict[str, Any],
) -> Any:
    """Hace un GET con reintentos y backoff exponencial; devuelve el JSON.

    Reintenta ante errores de conexión y códigos transitorios (429, 5xx). Usa
    ``logging`` (no prints). Es el único punto que toca la red, así que los tests
    mockean ``session.get`` aquí.

    Args:
        session: Sesión de ``requests`` (inyectable para tests).
        url: URL absoluta a consultar.
        params: Parámetros de query (se fuerza ``format=json``).

    Returns:
        El cuerpo JSON parseado (normalmente un array de 2 elementos).

    Raises:
        WorldBankAPIError: Si todos los intentos fallan.
    """
    merged = {"format": "json", **params}
    last_error: Exception | None = None

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = session.get(url, params=merged, timeout=30)
            if response.status_code in _RETRY_STATUS:
                raise requests.HTTPError(
                    f"status {response.status_code}", response=response
                )
            response.raise_for_status()
            return response.json()
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as exc:
            last_error = exc
            if attempt == _MAX_RETRIES:
                break
            sleep_for = _BACKOFF_BASE * (2 ** (attempt - 1))
            logger.warning(
                "World Bank API falló (intento %d/%d) en %s: %s. Reintento en %.1fs.",
                attempt,
                _MAX_RETRIES,
                url,
                exc,
                sleep_for,
            )
            time.sleep(sleep_for)

    raise WorldBankAPIError(
        f"World Bank API falló tras {_MAX_RETRIES} intentos en {url}: {last_error}"
    ) from last_error


def _split_payload(payload: Any) -> tuple[WBPageMeta, list[dict]]:
    """Desempaca el array de 2 elementos ``[metadata, [datos]]``.

    Args:
        payload: Cuerpo JSON de la API.

    Returns:
        Tupla ``(meta, registros)``. ``registros`` es ``[]`` si el segundo
        elemento es ``None`` (respuesta sin datos).

    Raises:
        WorldBankAPIError: Si el shape no es el array de 2 elementos esperado
            (p. ej. la API devuelve un mensaje de error como dict).
    """
    if not isinstance(payload, list) or len(payload) != 2:
        raise WorldBankAPIError(f"Shape inesperado de la API: {payload!r:.200}")
    meta_raw, data = payload
    meta = WBPageMeta(**meta_raw)
    records = data if isinstance(data, list) else []
    return meta, records


def _chunks(items: list[str], size: int) -> list[list[str]]:
    """Parte una lista en sublistas de tamaño ``size``."""
    return [items[i : i + size] for i in range(0, len(items), size)]


def fetch_lcn_countries(session: requests.Session | None = None) -> list[WBCountry]:
    """Obtiene los países de la región LCN (Latin America & Caribbean).

    El filtro ``region=LCN`` ya excluye agregados regionales; aun así se filtran
    defensivamente los registros marcados como ``Aggregates``.

    Args:
        session: Sesión de ``requests`` opcional (para tests). Si es ``None`` se
            crea una nueva.

    Returns:
        Lista de países reales de la región (sin agregados).
    """
    session = session or requests.Session()
    payload = _request_with_retry(
        session,
        f"{BASE_URL}/country",
        {"region": "LCN", "per_page": 300},
    )
    _meta, records = _split_payload(payload)
    countries = [WBCountry.from_api(r) for r in records]
    return [c for c in countries if not c.is_aggregate]


def fetch_indicator_page(
    session: requests.Session,
    iso3_codes: list[str],
    indicator_codes: list[str],
    date_range: str,
    page: int,
) -> tuple[WBPageMeta, list[WBObservation]]:
    """Obtiene una página de observaciones para países × indicadores dados.

    Agrupa los ISO3 con ``;`` y los indicadores con ``;`` usando ``source=2``.

    Args:
        session: Sesión de ``requests``.
        iso3_codes: Lista de códigos ISO3 (ya acotada a un chunk razonable).
        indicator_codes: Lista de códigos de indicador.
        date_range: Rango de años, p. ej. ``'2010:2024'``.
        page: Página a solicitar (1-indexed).

    Returns:
        Tupla ``(meta, observaciones)`` de esa página.
    """
    countries = ";".join(iso3_codes)
    indicators = ";".join(indicator_codes)
    payload = _request_with_retry(
        session,
        f"{BASE_URL}/country/{countries}/indicator/{indicators}",
        {"source": 2, "date": date_range, "per_page": 1000, "page": page},
    )
    meta, records = _split_payload(payload)
    observations = [WBObservation.from_api(r) for r in records]
    return meta, observations


def fetch_observations(
    iso3_codes: list[str],
    indicator_codes: tuple[str, ...] | list[str] = DEFAULT_INDICATORS,
    date_range: str = DEFAULT_DATE_RANGE,
    session: requests.Session | None = None,
) -> list[WBObservation]:
    """Obtiene TODAS las observaciones (manejando paginación y chunking).

    Itera las páginas de cada chunk de países hasta que ``page == pages``. Se
    landea todo crudo, incluidas observaciones con ``valor`` nulo (el filtrado
    es trabajo de dbt).

    Args:
        iso3_codes: Países a consultar (ISO3).
        indicator_codes: Indicadores a pedir. Por defecto los 4 del CLAUDE.md.
        date_range: Rango de años.
        session: Sesión de ``requests`` opcional (para tests).

    Returns:
        Todas las observaciones de todos los chunks y páginas.
    """
    session = session or requests.Session()
    indicators = list(indicator_codes)
    all_obs: list[WBObservation] = []

    for chunk in _chunks(iso3_codes, _COUNTRY_CHUNK):
        page = 1
        while True:
            meta, observations = fetch_indicator_page(
                session, chunk, indicators, date_range, page
            )
            all_obs.extend(observations)
            if page >= meta.pages:
                break
            page += 1

    logger.info(
        "Extraídas %d observaciones (%d países, %d indicadores).",
        len(all_obs),
        len(iso3_codes),
        len(indicators),
    )
    return all_obs

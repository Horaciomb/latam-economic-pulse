"""Carga cruda a PostgreSQL (capa L del EL).

Inserta las observaciones y países en los esquemas ``econ_raw`` con UPSERT
idempotente sobre las constraints UNIQUE. NO transforma datos de negocio (eso es
dbt). La conexión se recibe por parámetro (inyección de dependencias) para que
los tests usen un mock sin tocar una base real.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from psycopg2.extras import execute_values

from src.models.schemas import WBCountry, WBObservation

if TYPE_CHECKING:
    from psycopg2.extensions import connection as PgConnection

logger = logging.getLogger(__name__)

# UPSERT de observaciones: idempotente sobre (country_iso3, indicator_code, anio).
_UPSERT_OBSERVATIONS = """
    INSERT INTO econ_raw.wb_observations
        (country_iso3, country_name, indicator_code, indicator_name, anio, valor)
    VALUES %s
    ON CONFLICT (country_iso3, indicator_code, anio) DO UPDATE SET
        country_name   = EXCLUDED.country_name,
        indicator_name = EXCLUDED.indicator_name,
        valor          = EXCLUDED.valor,
        ingested_at    = now()
"""

# UPSERT de países: idempotente sobre (country_iso3).
_UPSERT_COUNTRIES = """
    INSERT INTO econ_raw.wb_countries
        (country_iso3, iso2, name, region, income_level, capital, longitude, latitude)
    VALUES %s
    ON CONFLICT (country_iso3) DO UPDATE SET
        iso2         = EXCLUDED.iso2,
        name         = EXCLUDED.name,
        region       = EXCLUDED.region,
        income_level = EXCLUDED.income_level,
        capital      = EXCLUDED.capital,
        longitude    = EXCLUDED.longitude,
        latitude     = EXCLUDED.latitude,
        ingested_at  = now()
"""


def upsert_observations(conn: PgConnection, rows: list[WBObservation]) -> int:
    """Inserta/actualiza observaciones de indicadores de forma idempotente.

    Reejecutar con los mismos datos no duplica filas: el ``ON CONFLICT`` actualiza
    la fila existente. Se cargan todas las observaciones crudas, incluidas las de
    ``valor`` nulo (el descarte es trabajo de dbt en staging).

    Args:
        conn: Conexión psycopg2 abierta (inyectada; en tests, un mock).
        rows: Observaciones a cargar.

    Returns:
        El número de observaciones procesadas.
    """
    if not rows:
        logger.info("Sin observaciones para cargar.")
        return 0

    values = [
        (
            r.country_iso3,
            r.country_name,
            r.indicator_code,
            r.indicator_name,
            r.anio,
            r.valor,
        )
        for r in rows
    ]
    with conn.cursor() as cur:
        execute_values(cur, _UPSERT_OBSERVATIONS, values)
    logger.info("Upsert de %d observaciones en econ_raw.wb_observations.", len(values))
    return len(values)


def upsert_countries(conn: PgConnection, rows: list[WBCountry]) -> int:
    """Inserta/actualiza países de forma idempotente sobre el ISO3.

    Args:
        conn: Conexión psycopg2 abierta (inyectada; en tests, un mock).
        rows: Países a cargar.

    Returns:
        El número de países procesados.
    """
    if not rows:
        logger.info("Sin países para cargar.")
        return 0

    values = [
        (
            c.country_iso3,
            c.iso2,
            c.name,
            c.region,
            c.income_level,
            c.capital,
            c.longitude,
            c.latitude,
        )
        for c in rows
    ]
    with conn.cursor() as cur:
        execute_values(cur, _UPSERT_COUNTRIES, values)
    logger.info("Upsert de %d países en econ_raw.wb_countries.", len(values))
    return len(values)

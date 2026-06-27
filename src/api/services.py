"""Capa de servicios: SQL parametrizado contra los marts dbt (esquema econ).

Toda la lógica de acceso a datos vive aquí; los routers sólo delegan. Las
consultas usan parámetros (nunca interpolación de strings) para evitar inyección.
"""

from __future__ import annotations

from src.api.database import get_cursor


def list_indicators() -> list[dict]:
    """Catálogo de indicadores disponibles (de dim_indicator).

    Returns:
        Lista de indicadores ordenada por código.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT indicator_code, indicator_name, unit, category, description_es
            FROM dim_indicator
            ORDER BY indicator_code
            """
        )
        return cur.fetchall()


def list_countries() -> list[dict]:
    """Catálogo de países disponibles (de dim_country).

    Returns:
        Lista de países ordenada por nombre.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT country_iso3, country_name, iso2, region,
                   income_level, capital, longitude, latitude
            FROM dim_country
            ORDER BY country_name
            """
        )
        return cur.fetchall()


def get_country_series(iso3: str) -> list[dict]:
    """Serie temporal de todos los indicadores de un país.

    Args:
        iso3: Código ISO3 del país (case-insensitive).

    Returns:
        Observaciones del país ordenadas por indicador y año.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT country_iso3, indicator_code, anio, valor
            FROM fct_indicators
            WHERE country_iso3 = upper(%(iso3)s)
            ORDER BY indicator_code, anio
            """,
            {"iso3": iso3},
        )
        return cur.fetchall()


def get_country_indicator_series(iso3: str, indicator_code: str) -> list[dict]:
    """Serie temporal de un indicador para un país.

    Args:
        iso3: Código ISO3 del país.
        indicator_code: Código del indicador.

    Returns:
        Observaciones ordenadas por año.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT country_iso3, indicator_code, anio, valor
            FROM fct_indicators
            WHERE country_iso3 = upper(%(iso3)s)
              AND indicator_code = %(code)s
            ORDER BY anio
            """,
            {"iso3": iso3, "code": indicator_code},
        )
        return cur.fetchall()


def get_latest_by_indicator(indicator_code: str) -> list[dict]:
    """Último valor de un indicador en todos los países (ranking).

    Args:
        indicator_code: Código del indicador.

    Returns:
        Últimos valores por país, ordenados de mayor a menor.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT country_iso3, indicator_code, anio, valor
            FROM mart_latest_indicators
            WHERE indicator_code = %(code)s
            ORDER BY valor DESC NULLS LAST
            """,
            {"code": indicator_code},
        )
        return cur.fetchall()


def compare_countries(iso3_codes: list[str], indicator_code: str) -> list[dict]:
    """Comparativa de un indicador entre varios países (serie completa).

    Args:
        iso3_codes: Lista de códigos ISO3 a comparar.
        indicator_code: Código del indicador.

    Returns:
        Observaciones de los países dados, ordenadas por país y año.
    """
    upper_codes = [c.strip().upper() for c in iso3_codes if c.strip()]
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT country_iso3, indicator_code, anio, valor
            FROM fct_indicators
            WHERE indicator_code = %(code)s
              AND country_iso3 = ANY(%(codes)s)
            ORDER BY country_iso3, anio
            """,
            {"code": indicator_code, "codes": upper_codes},
        )
        return cur.fetchall()


def get_indicator_stats(indicator_code: str) -> dict | None:
    """Estadísticos (min/max/promedio) de un indicador en su último año disponible.

    Usa mart_latest_indicators para reflejar el dato más reciente de cada país.

    Args:
        indicator_code: Código del indicador.

    Returns:
        Dict con ``count``, ``min_valor``, ``max_valor``, ``avg_valor`` y el
        ``anio`` máximo observado; ``None`` si no hay datos.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT
                %(code)s          AS indicator_code,
                max(anio)         AS anio,
                count(valor)      AS count,
                min(valor)        AS min_valor,
                max(valor)        AS max_valor,
                avg(valor)        AS avg_valor
            FROM mart_latest_indicators
            WHERE indicator_code = %(code)s
            """,
            {"code": indicator_code},
        )
        row = cur.fetchone()
    if not row or row["count"] == 0:
        return None
    return row

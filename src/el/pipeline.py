"""Orquestación del EL: extract → load. La transformación (T) la hace dbt.

Lee ``DATABASE_URL`` del entorno, abre una conexión a la instancia Supabase
compartida, extrae países e indicadores de la World Bank API y los carga crudos
en ``econ_raw``. Es la ÚNICA pieza que toca la base real; ``extract`` y ``load``
son inyectables para mantenerla testeable.

Uso:
    python -m src.el.pipeline
"""

from __future__ import annotations

import logging
import os

import psycopg2

from src.el.extract import (
    DEFAULT_DATE_RANGE,
    DEFAULT_INDICATORS,
    fetch_lcn_countries,
    fetch_observations,
)
from src.el.load import upsert_countries, upsert_observations

logger = logging.getLogger(__name__)


def run_pipeline(
    database_url: str | None = None,
    indicators: tuple[str, ...] = DEFAULT_INDICATORS,
    date_range: str = DEFAULT_DATE_RANGE,
) -> dict[str, int]:
    """Ejecuta el EL completo: extrae de la API y carga crudo en econ_raw.

    Args:
        database_url: Connection string. Si es ``None`` se lee de ``DATABASE_URL``.
        indicators: Indicadores a extraer. Por defecto los 4 del CLAUDE.md.
        date_range: Rango de años, p. ej. ``'2010:2024'``.

    Returns:
        Conteos cargados: ``{"countries": n, "observations": m}``.

    Raises:
        RuntimeError: Si no hay ``DATABASE_URL`` disponible.
    """
    database_url = database_url or os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "Falta DATABASE_URL. Expórtala antes de correr el pipeline "
            "(ver .env.example)."
        )

    logger.info("Extrayendo catálogo de países de la región LCN...")
    countries = fetch_lcn_countries()
    iso3_codes = [c.country_iso3 for c in countries]
    logger.info("%d países en la región.", len(iso3_codes))

    logger.info("Extrayendo observaciones de %d indicadores...", len(indicators))
    observations = fetch_observations(
        iso3_codes, indicator_codes=indicators, date_range=date_range
    )

    # search_path=econ_raw: las sentencias de load apuntan ahí explícitamente,
    # pero lo fijamos para dejar claro el contexto del landing.
    conn = psycopg2.connect(database_url, options="-c search_path=econ_raw")
    try:
        n_countries = upsert_countries(conn, countries)
        n_obs = upsert_observations(conn, observations)
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("El pipeline falló; se hizo rollback.")
        raise
    finally:
        conn.close()

    result = {"countries": n_countries, "observations": n_obs}
    logger.info("Pipeline EL completado: %s", result)
    return result


def main() -> None:
    """Punto de entrada CLI: configura logging y corre el pipeline."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    run_pipeline()


if __name__ == "__main__":
    main()

"""Conexión a PostgreSQL para el API (lee de los marts dbt en el esquema econ).

Mantiene un pool de conexiones psycopg2 con ``search_path=econ`` para que los
servicios consulten los modelos dbt sin calificar el esquema. Las credenciales
salen sólo del entorno (``DATABASE_URL``).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

import psycopg2.extras
from psycopg2.pool import SimpleConnectionPool

if TYPE_CHECKING:
    from psycopg2.extensions import connection as PgConnection

_pool: SimpleConnectionPool | None = None


def init_pool(minconn: int = 1, maxconn: int = 5) -> None:
    """Inicializa el pool de conexiones (idempotente).

    Args:
        minconn: Conexiones mínimas del pool.
        maxconn: Conexiones máximas del pool.

    Raises:
        RuntimeError: Si no hay ``DATABASE_URL`` en el entorno.
    """
    global _pool
    if _pool is not None:
        return
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("Falta DATABASE_URL para inicializar el pool del API.")
    _pool = SimpleConnectionPool(
        minconn,
        maxconn,
        dsn=database_url,
        options="-c search_path=econ",
    )


def close_pool() -> None:
    """Cierra todas las conexiones del pool."""
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None


@contextmanager
def get_cursor() -> Iterator[psycopg2.extras.RealDictCursor]:
    """Entrega un cursor que devuelve filas como dicts, gestionando la conexión.

    Yields:
        Un ``RealDictCursor`` listo para consultas de sólo lectura.

    Raises:
        RuntimeError: Si el pool no fue inicializado con :func:`init_pool`.
    """
    if _pool is None:
        raise RuntimeError("Pool no inicializado. Llama init_pool() primero.")
    conn: PgConnection = _pool.getconn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)


def ping() -> bool:
    """Verifica la conexión a la base (para el endpoint /health).

    Returns:
        ``True`` si ``SELECT 1`` responde correctamente.
    """
    with get_cursor() as cur:
        cur.execute("SELECT 1 AS ok")
        row = cur.fetchone()
    return bool(row and row.get("ok") == 1)

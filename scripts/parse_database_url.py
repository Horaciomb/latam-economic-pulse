"""Deriva las 5 variables PG* que necesita dbt-postgres desde DATABASE_URL.

dbt-postgres NO acepta una connection string: requiere campos discretos (host,
port, user, pass, dbname). Para mantener ``DATABASE_URL`` como única fuente de
verdad (lo usa Python), este script la parsea y emite las variables PG* en
formato ``KEY=value``, listo para volcar a ``$GITHUB_ENV`` (CI) o a ``eval`` /
un ``.env`` en local.

Uso:
    # CI (GitHub Actions):
    python scripts/parse_database_url.py >> "$GITHUB_ENV"

    # Local (bash):
    eval "$(python scripts/parse_database_url.py --export)"
    cd dbt && dbt debug
"""

from __future__ import annotations

import argparse
import os
import sys
from urllib.parse import unquote, urlsplit


def derive_pg_env(database_url: str) -> dict[str, str]:
    """Descompone una URL postgres en las variables PG* discretas.

    Args:
        database_url: Connection string, p. ej.
            ``postgresql://user:pass@host:5432/postgres?sslmode=require``.

    Returns:
        Dict con ``PGHOST``, ``PGPORT``, ``PGUSER``, ``PGPASSWORD``,
        ``PGDATABASE`` (los campos presentes en la URL).

    Raises:
        ValueError: Si la URL no trae host o nombre de base de datos.
    """
    parts = urlsplit(database_url)
    if not parts.hostname or not parts.path.lstrip("/"):
        raise ValueError("DATABASE_URL inválida: falta host o nombre de base de datos.")

    env = {
        "PGHOST": parts.hostname,
        "PGPORT": str(parts.port or 5432),
        "PGDATABASE": parts.path.lstrip("/"),
    }
    if parts.username:
        env["PGUSER"] = unquote(parts.username)
    if parts.password:
        env["PGPASSWORD"] = unquote(parts.password)
    return env


def main() -> int:
    """CLI: imprime las variables PG* en formato KEY=value."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--export",
        action="store_true",
        help="Prefija cada línea con 'export ' (para eval en bash).",
    )
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: falta DATABASE_URL en el entorno.", file=sys.stderr)
        return 1

    try:
        env = derive_pg_env(database_url)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    prefix = "export " if args.export else ""
    for key, value in env.items():
        print(f"{prefix}{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

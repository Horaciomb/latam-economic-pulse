"""Tests del helper que deriva las variables PG* desde DATABASE_URL."""

from __future__ import annotations

import pytest

from scripts.parse_database_url import derive_pg_env


def test_basic_url():
    env = derive_pg_env(
        "postgresql://user:pass@db.abc.supabase.co:5432/postgres?sslmode=require"
    )
    assert env == {
        "PGHOST": "db.abc.supabase.co",
        "PGPORT": "5432",
        "PGDATABASE": "postgres",
        "PGUSER": "user",
        "PGPASSWORD": "pass",
    }


def test_url_decodes_special_chars_in_password():
    """Contraseñas con caracteres especiales vienen percent-encoded."""
    env = derive_pg_env("postgresql://u:p%40ss%21@host:6543/mydb")
    assert env["PGPASSWORD"] == "p@ss!"
    assert env["PGPORT"] == "6543"


def test_default_port_when_missing():
    env = derive_pg_env("postgresql://u:p@host/postgres")
    assert env["PGPORT"] == "5432"


def test_invalid_url_raises():
    with pytest.raises(ValueError):
        derive_pg_env("postgresql://user:pass@/")  # sin host ni dbname

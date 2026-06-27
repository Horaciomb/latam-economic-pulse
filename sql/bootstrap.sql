-- =============================================================================
-- bootstrap.sql — Latam Economic Pulse
-- =============================================================================
-- Crea los esquemas y las tablas crudas (landing zone) en la instancia Supabase
-- COMPARTIDA ya existente. NO crea un proyecto nuevo.
--
-- Ejecutar UNA sola vez, manualmente, con tu DATABASE_URL:
--     psql "$DATABASE_URL" -f sql/bootstrap.sql
--
-- Esquemas:
--   econ_raw → datos crudos cargados por Python (este archivo).
--   econ     → modelos transformados por dbt (dbt los gestiona; aquí solo se crea).
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS econ_raw;
CREATE SCHEMA IF NOT EXISTS econ;

-- -----------------------------------------------------------------------------
-- econ_raw.wb_observations — observaciones crudas de indicadores (grano
-- país × indicador × año). Se cargan TAL CUAL vienen de la API, incluyendo
-- valores NULL (World Bank deja huecos). El descarte de NULLs es trabajo de dbt.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS econ_raw.wb_observations (
    country_iso3    text        NOT NULL,
    country_name    text,
    indicator_code  text        NOT NULL,
    indicator_name  text,
    anio            integer     NOT NULL,
    valor           numeric,                         -- NULL permitido (huecos World Bank)
    ingested_at     timestamptz NOT NULL DEFAULT now(),

    -- Idempotencia: una observación por país × indicador × año. Habilita UPSERT.
    CONSTRAINT uq_wb_observations UNIQUE (country_iso3, indicator_code, anio)
);

-- -----------------------------------------------------------------------------
-- econ_raw.wb_countries — catálogo crudo de países de la región LCN
-- (Latin America & Caribbean). Enriquece dim_country con región, nivel de
-- ingreso y geo. Grano: un registro por país (ISO3).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS econ_raw.wb_countries (
    country_iso3    text        NOT NULL,
    iso2            text,
    name            text,
    region          text,                            -- ya viene normalizada (sin espacios)
    income_level    text,
    capital         text,
    longitude       numeric,
    latitude        numeric,
    ingested_at     timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT uq_wb_countries UNIQUE (country_iso3)
);

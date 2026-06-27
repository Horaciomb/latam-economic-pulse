# Latam Economic Pulse API

![CI](https://github.com/USUARIO/latam-economic-pulse/actions/workflows/ci.yml/badge.svg)
![dbt docs](https://github.com/USUARIO/latam-economic-pulse/actions/workflows/dbt-docs.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![dbt](https://img.shields.io/badge/dbt-core%201.9-orange)

Pipeline de datos que extrae indicadores económicos de toda Latinoamérica desde la
**World Bank Indicators API v2**, los carga crudos a PostgreSQL, los transforma con
**dbt** (arquitectura por capas, tests, documentación y lineage) y los expone con una
**API REST en FastAPI**.

> Segundo proyecto de portafolio de Ingeniería de Datos. El foco es **dbt**: modelos
> en capas (staging → marts), tests, docs públicas y lineage sobre un modelo dimensional.

📊 **Documentación dbt (lineage + catálogo):** https://USUARIO.github.io/latam-economic-pulse/

---

## Arquitectura

```
┌──────────────────┐   EL (Python)        ┌──────────────────┐   T (dbt)         ┌──────────────────┐
│  World Bank API  │ ───────────────────► │   econ_raw       │ ────────────────► │   econ           │
│  (v2, sin key)   │  requests + pandas   │  (landing crudo) │  staging → marts  │  modelo          │
│                  │  upsert idempotente  │  wb_observations │  views → tables   │  dimensional     │
└──────────────────┘                      │  wb_countries    │                   │  dim/fct/mart    │
                                          └──────────────────┘                   └────────┬─────────┘
                                                                                           │
                                                                              ┌────────────▼─────────┐
                                                                              │  FastAPI (sólo lee)  │
                                                                              │  /indicators /latest │
                                                                              │  /compare /stats ... │
                                                                              └──────────────────────┘
```

**Separación clave:** Python hace **sólo EL** (extract + load crudo). **Toda la
transformación vive en dbt** — es deliberado, para mostrar dbt como pieza central.

### Lineage dbt

```
source: econ_raw.wb_observations ─► stg_wb_observations ─┬─► dim_country ◄─┐
source: econ_raw.wb_countries ────► stg_wb_countries ────┘                 │
                                                          ├─► fct_indicators ─► mart_latest_indicators
seed:   indicator_metadata ───────────────────────────────► dim_indicator ◄┘
```

---

## Modelo de datos

| Capa | Esquema | Objeto | Materialización | Descripción |
|------|---------|--------|-----------------|-------------|
| Landing | `econ_raw` | `wb_observations` | tabla (Python) | Observaciones crudas país×indicador×año (incluye nulos). |
| Landing | `econ_raw` | `wb_countries` | tabla (Python) | Catálogo de países LCN (región, ingreso, geo). |
| Staging | `econ` | `stg_wb_observations` | view | Tipos limpios; **descarta valores nulos**. |
| Staging | `econ` | `stg_wb_countries` | view | Texto normalizado. |
| Marts | `econ` | `dim_country` | table | Dimensión país enriquecida. |
| Marts | `econ` | `dim_indicator` | table | Dimensión indicador (+ seed de metadata). |
| Marts | `econ` | `fct_indicators` | table | Hechos país×indicador×año, FKs a dims. |
| Marts | `econ` | `mart_latest_indicators` | table | Último valor por país×indicador. |

---

## Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/` | Info + enlaces a `/docs` y dbt docs. |
| GET | `/health` | Estado del API + conexión a la base. |
| GET | `/indicators` | Catálogo de indicadores. |
| GET | `/countries` | Catálogo de países. |
| GET | `/indicators/{iso3}` | Serie temporal de todos los indicadores de un país. |
| GET | `/indicators/{iso3}/{code}` | Serie de un indicador de un país. |
| GET | `/latest?indicator=FP.CPI.TOTL.ZG` | Último valor del indicador en todos los países (ranking). |
| GET | `/compare?countries=BOL;PER;BRA&indicator=NY.GDP.MKTP.CD` | Comparativa entre países. |
| GET | `/stats/{code}` | min/max/promedio del indicador en la región. |

---

## Setup

### 1. Requisitos
- Python 3.11+ (dbt-core 1.9 no soporta 3.13+).
- Acceso a una instancia PostgreSQL (este proyecto usa una instancia Supabase
  **compartida**, en los esquemas `econ_raw` y `econ`).

### 2. Instalar
```bash
python -m venv venv
source venv/Scripts/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configurar entorno
```bash
cp .env.example .env
# Editar .env con tu DATABASE_URL (conexión directa / session, puerto 5432).
```

### 4. Crear esquemas y tablas crudas (una vez)
```bash
psql "$DATABASE_URL" -f sql/bootstrap.sql
```

### 5. Correr el EL (carga cruda)
```bash
python -m src.el.pipeline
```

### 6. Transformar con dbt
```bash
# Derivar las variables PG* que necesita dbt desde DATABASE_URL:
eval "$(python scripts/parse_database_url.py --export)"

cd dbt
dbt deps          # instala dbt_utils
dbt debug         # verifica conexión
dbt seed          # carga indicator_metadata.csv
dbt build         # run + test (debe pasar limpio)
dbt docs generate # catálogo + lineage
```

### 7. Levantar el API
```bash
uvicorn src.api.main:app --reload
# Swagger en http://localhost:8000/docs
```

---

## Tests y calidad
```bash
pytest          # tests de extract / load / API (con mocks, sin DB ni red)
ruff check .    # linting
cd dbt && dbt build   # tests de dbt (not_null, unique, relationships, accepted_values)
```

---

## Decisiones de diseño

### 1. Un único esquema `econ` para todo dbt
La instancia Supabase es **compartida** (ya tiene `public`, `polla`, `fx`). Para
mantener el namespace ordenado, una macro [`generate_schema_name`](dbt/macros/generate_schema_name.sql)
fuerza que **todos** los modelos (staging y marts) se materialicen en `econ`, en
lugar del comportamiento por defecto de dbt que crearía `econ_staging` y `econ_marts`.

### 2. `DATABASE_URL` → variables `PG*` para dbt
`dbt-postgres` **no acepta una connection string**: exige campos discretos (host,
port, user, pass, dbname). Para mantener `DATABASE_URL` como **única fuente de
verdad** (lo usa Python), el script [`scripts/parse_database_url.py`](scripts/parse_database_url.py)
la descompone en las 5 variables `PG*` justo antes de correr dbt — en CI y en local.
`profiles.yml` las lee con `env_var()`. **Cero credenciales hardcodeadas.**

### 3. Conexión directa, no transaction pooler
En Supabase, dbt usa la conexión **directa / session-mode (puerto 5432)**, no el
transaction pooler (6543): dbt necesita features de sesión (temp tables, `SET`).

### 4. El descarte de nulos es trabajo de dbt
La World Bank API deja huecos (`value: null`). Python **landea todo crudo** en
`econ_raw` (fidelidad y re-runs completos); el filtrado ocurre en `stg_wb_observations`.
La decisión queda documentada en el modelo, no enterrada en código Python.

---

## Stack

Python 3.11 · requests · pandas · **dbt-core + dbt-postgres** · PostgreSQL (Supabase) ·
FastAPI · pydantic v2 · pytest · ruff · GitHub Actions · GitHub Pages.

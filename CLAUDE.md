# CLAUDE.md — Latam Economic Pulse API

## Propósito del proyecto

Pipeline de datos que extrae indicadores económicos de toda Latinoamérica desde
la API pública del Banco Mundial (World Bank), los carga crudos a PostgreSQL,
los transforma con **dbt** siguiendo una arquitectura por capas (staging → marts),
publica la documentación del modelo con **dbt docs en GitHub Pages**, y expone los
datos limpios mediante una API REST con FastAPI.

Este es el segundo proyecto de portafolio de Ingeniería de Datos. A diferencia
del proyecto 1 (ETL simple), aquí el foco es demostrar **dbt** (modelos, tests,
documentación, lineage) y el manejo de datos multi-país/multi-indicador. dbt es
el skill más demandado que se busca reforzar con este proyecto.

## Contexto del autor (para no re-explicar)

El autor ya completó un proyecto previo (Bolivia Exchange Tracker) con este mismo
flujo: Python ETL + FastAPI + PostgreSQL en Supabase + GitHub Actions. Reutiliza
ese conocimiento. La novedad real de este proyecto es dbt. NO es necesario
re-justificar FastAPI ni el patrón de tests; sí documentar bien todo lo de dbt.

## Stack tecnológico (NO cambiar sin justificación)

- **Lenguaje:** Python 3.11+
- **Extracción/carga (EL):** requests + pandas → carga cruda a PostgreSQL
- **Transformación (T):** **dbt-core + dbt-postgres** (la pieza central)
- **Base de datos:** PostgreSQL en Supabase, **esquema dedicado `econ`** dentro de
  la MISMA instancia compartida (ya tiene los esquemas `public`, `polla`, `fx`).
  Conexión directa vía `DATABASE_URL` con psycopg2/SQLAlchemy. NO usar supabase-py.
- **API:** FastAPI + uvicorn
- **Validación:** pydantic v2
- **Tests Python:** pytest
- **Orquestación:** GitHub Actions (cron semanal para el EL + dbt run)
- **Docs dbt:** dbt docs generate → publicados en GitHub Pages
- **Deploy API:** Render.com (free tier)
- **Linting:** ruff

## Fuente de datos — World Bank Indicators API v2

API pública, gratuita, **sin API key**, formato JSON.

- Base URL: `https://api.worldbank.org/v2`
- No requiere autenticación (confirmado en docs oficiales).
- Formato JSON: agregar `?format=json` a toda llamada.
- La respuesta JSON es un ARRAY de 2 elementos: `[ metadata, [ ...datos ] ]`.
  El primer elemento tiene paginación (page, pages, per_page, total). El segundo
  es la lista de observaciones. HAY QUE manejar la paginación (per_page alto, ej.
  `per_page=1000`, y/o iterar las páginas).

### Países: usar el agregado regional LCN
Para "toda Latinoamérica" NO listar país por país. El World Bank tiene el código
de región `LCN` (Latin America & Caribbean). Pero ojo: pedir el indicador para la
región LCN devuelve el agregado regional, no cada país. Para obtener país POR país
de la región, primero obtener la lista de países de la región:

  `GET /v2/country?region=LCN&format=json&per_page=100`

De ahí extraer los `id` (ISO3) de cada país (excluir agregados donde
`region.value == "Aggregates"`). Luego pedir los indicadores para esos países.

Se pueden pedir varios países juntos separando los ISO3 con `;`:
  `GET /v2/country/BOL;PER;BRA/indicator/NY.GDP.MKTP.CD?format=json`

### Indicadores a extraer (mínimo 4, ampliable)
| Código indicador      | Significado                          |
|-----------------------|--------------------------------------|
| NY.GDP.MKTP.CD        | PIB (US$ corrientes)                 |
| FP.CPI.TOTL.ZG        | Inflación, precios consumidor (% anual) |
| SL.UEM.TOTL.ZS        | Desempleo (% de fuerza laboral)      |
| NY.GDP.PCAP.CD        | PIB per cápita (US$ corrientes)      |

Se pueden pedir múltiples indicadores de una fuente con `;` y `source=2`:
  `GET /v2/country/BOL/indicator/NY.GDP.MKTP.CD;FP.CPI.TOTL.ZG?source=2&format=json`

Rango temporal sugerido: últimos ~15 años. Usar `date=2010:2024`.

NOTA: hacer un curl real a la API antes de modelar. Confirmar el shape exacto del
JSON (campos `countryiso3code`, `country.value`, `indicator.id`, `date`, `value`,
que pueden venir con null en `value`).

## Arquitectura del repositorio

```
latam-economic-pulse/
├── .github/workflows/
│   ├── ci.yml               # ruff + pytest + dbt build (en cada push/PR)
│   ├── pipeline.yml         # cron semanal: EL python + dbt run + dbt test
│   └── dbt-docs.yml         # genera y publica dbt docs a GitHub Pages
├── src/
│   ├── el/
│   │   ├── __init__.py
│   │   ├── extract.py       # llama World Bank API, maneja paginación
│   │   ├── load.py          # carga cruda a econ_raw.wb_observations (upsert)
│   │   └── pipeline.py      # orquesta extract→load (solo EL; la T la hace dbt)
│   ├── models/
│   │   └── schemas.py       # pydantic para validar la extracción
│   └── api/
│       ├── __init__.py
│       ├── main.py
│       ├── database.py      # pool psycopg2, search_path econ
│       ├── schemas.py       # modelos de respuesta tipados
│       ├── services.py      # SQL contra las tablas/vistas de marts dbt
│       └── routers/
│           ├── indicators.py
│           └── stats.py
├── dbt/                     # proyecto dbt
│   ├── dbt_project.yml
│   ├── profiles.yml         # usa env var DATABASE_URL (NO credenciales hardcoded)
│   ├── models/
│   │   ├── staging/
│   │   │   ├── _staging.yml         # sources + tests + docs de staging
│   │   │   └── stg_wb_observations.sql
│   │   └── marts/
│   │       ├── _marts.yml           # tests + docs de los marts
│   │       ├── fct_indicators.sql   # tabla de hechos: país×indicador×año
│   │       ├── dim_country.sql      # dimensión país
│   │       ├── dim_indicator.sql    # dimensión indicador
│   │       └── mart_latest_indicators.sql  # último valor por país×indicador
│   └── tests/                       # tests singulares dbt si hacen falta
├── tests/                   # tests pytest del EL y la API
│   ├── test_extract.py
│   ├── test_load.py
│   └── test_api.py
├── sql/
│   └── bootstrap.sql        # crea esquemas econ y econ_raw + tabla raw
├── .env.example
├── requirements.txt
├── pyproject.toml
├── README.md
└── CLAUDE.md
```

## Modelo de datos y capas

### Esquemas en PostgreSQL (instancia compartida)
- `econ_raw` → datos crudos cargados por Python (landing zone)
- `econ` → modelos transformados por dbt (staging materializa como views,
  marts como tables). Configurar esto en dbt_project.yml.

dbt escribe en el esquema `econ`. Configurar el `profiles.yml` con
`schema: econ`. Si dbt genera sufijos de esquema por capa (ej. econ_staging),
usar una macro `generate_schema_name` que respete un esquema único `econ` para
mantener todo ordenado en la instancia compartida. Documentar esta decisión.

### Landing (Python) — econ_raw.wb_observations
| Columna          | Tipo          | Notas                                  |
|------------------|---------------|----------------------------------------|
| country_iso3     | text          | ej. 'BOL'                              |
| country_name     | text          |                                        |
| indicator_code   | text          | ej. 'NY.GDP.MKTP.CD'                    |
| indicator_name   | text          |                                        |
| anio             | int           | año de la observación                  |
| valor            | numeric       | puede ser NULL (World Bank deja huecos)|
| ingested_at      | timestamptz   | default now()                          |

Constraint idempotencia: UNIQUE(country_iso3, indicator_code, anio). UPSERT.

### Capa staging (dbt) — stg_wb_observations
- Lee de la source `econ_raw.wb_observations`.
- Limpia tipos, normaliza nombres, castea año a int, descarta filas con valor NULL
  (o las marca, documentar la decisión).
- Materialización: view.
- Tests: not_null en claves, accepted_values en indicator_code.

### Capa marts (dbt) — modelo dimensional
- `dim_country`: un registro por país (iso3, nombre, región).
- `dim_indicator`: un registro por indicador (código, nombre, unidad).
- `fct_indicators`: tabla de hechos grano país×indicador×año, con FKs a las dims.
- `mart_latest_indicators`: último valor disponible por país×indicador (para que
  la API responda rápido "el dato más reciente").
- Materialización: table.
- Tests: relationships (FK fct→dim), unique en las dims, not_null.

## Endpoints del API (leen de los marts dbt)

- `GET /` → info + link a /docs y a la dbt docs en GitHub Pages
- `GET /health` → status API + conexión DB
- `GET /indicators` → catálogo de indicadores disponibles (de dim_indicator)
- `GET /countries` → catálogo de países (de dim_country)
- `GET /indicators/{iso3}` → todos los indicadores de un país (serie temporal)
- `GET /indicators/{iso3}/{indicator_code}` → serie de un indicador de un país
- `GET /latest?indicator=FP.CPI.TOTL.ZG` → último valor de ese indicador en todos
  los países (ranking), leyendo de mart_latest_indicators
- `GET /compare?countries=BOL;PER;BRA&indicator=NY.GDP.MKTP.CD` → comparativa
- `GET /stats/{indicator_code}` → min/max/promedio del indicador en la región

Todos los modelos de respuesta tipados con pydantic para que /docs (Swagger) salga
profesional.

## Convenciones de código

- Type hints en todas las funciones públicas. Docstrings estilo Google.
- Sin lógica de negocio en routers — delegar a services.
- Extracción con reintentos (3x, backoff) y logging (no prints).
- Credenciales SOLO desde entorno. Nunca hardcodear la connection string, ni en
  profiles.yml de dbt (usar `"{{ env_var('DATABASE_URL') }}"`).
- Conventional commits.

## Convenciones dbt (importante para la calidad del proyecto)

- TODO modelo debe tener su entrada en el .yml correspondiente con `description`
  por modelo y por columna (esto alimenta la documentación pública).
- TODO modelo de marts debe tener al menos un test (unique/not_null/relationships).
- Usar `ref()` y `source()` siempre — nunca nombres de tabla hardcodeados.
- staging = views, marts = tables (configurar en dbt_project.yml).
- Nombres: stg_ para staging, dim_/fct_/mart_ para marts.
- `dbt build` (que corre run + test) debe pasar limpio antes de cualquier merge.

## Tests Python requeridos (mínimo)

- test_extract.py: mock de la API World Bank (incluido el formato array de 2
  elementos y la paginación), verificar reintentos.
- test_load.py: lógica de upsert idempotente (con mocks, sin DB real).
- test_api.py: cada endpoint retorna 200 y el shape esperado (services mockeados).

## Lo que NO debe hacer Claude Code

- NO crear un proyecto Supabase nuevo. Reutiliza la instancia existente, esquemas
  `econ` y `econ_raw`. El usuario ejecuta bootstrap.sql y pasa el DATABASE_URL.
- NO hardcodear credenciales en ningún lado (ni en profiles.yml).
- NO inventar el formato de la API — hacer curl real primero.
- NO meter la transformación en Python: la T es responsabilidad de dbt. Python
  solo extrae y carga crudo (EL). Esto es deliberado para mostrar dbt.
- NO sobre-ingenierizar: nada de Airflow/Dagster. Orquestación = GitHub Actions.
- NO commitear .env ni target/ ni dbt_packages/ (agregar a .gitignore).

## Orden de implementación sugerido

1. Setup: requirements.txt (incluir dbt-core, dbt-postgres), pyproject.toml,
   .gitignore, .env.example, estructura de carpetas.
2. curl real a la World Bank API: lista de países LCN + un indicador. Confirmar shape.
3. sql/bootstrap.sql: esquemas econ_raw y econ + tabla wb_observations.
4. models/schemas.py (pydantic) para la extracción.
5. el/extract.py + test (con la paginación y el array de 2 elementos mockeados).
6. el/load.py (upsert idempotente) + test.
7. el/pipeline.py (orquesta EL). Correr localmente y verificar carga cruda.
8. Proyecto dbt: dbt_project.yml + profiles.yml (env var). Verificar `dbt debug`.
9. Source + staging model + sus tests. `dbt run --select staging` + `dbt test`.
10. Marts (dims, fct, latest) + tests. `dbt build`.
11. dbt docs generate — verificar que el catálogo y el lineage se generen.
12. api/ completa leyendo de los marts.
13. tests/test_api.py.
14. Workflows: ci.yml, pipeline.yml (cron semanal), dbt-docs.yml (GitHub Pages).
15. README con badges, diagrama de arquitectura (EL→dbt→API), enlace a dbt docs,
    e instrucciones de setup.

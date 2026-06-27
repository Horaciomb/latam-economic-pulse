-- Dimensión país: un registro por ISO3. Se enriquece con el catálogo de países
-- (región, nivel de ingreso, capital, geo). Sólo incluye países que tienen al
-- menos una observación, para que las FKs de fct_indicators siempre resuelvan.

with countries as (

    select * from {{ ref('stg_wb_countries') }}

),

observed as (

    -- Países presentes en los hechos, con el nombre tal como lo reporta la API
    -- de indicadores (fallback si el catálogo no lo trae).
    select
        country_iso3,
        max(country_name) as country_name
    from {{ ref('stg_wb_observations') }}
    group by country_iso3

)

select
    observed.country_iso3,
    coalesce(countries.country_name, observed.country_name) as country_name,
    countries.iso2,
    countries.region,
    countries.income_level,
    countries.capital,
    countries.longitude,
    countries.latitude
from observed
left join countries using (country_iso3)

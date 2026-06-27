-- Staging de observaciones: limpia tipos y normaliza desde el landing crudo.
-- Decisión: se DESCARTAN las filas con valor nulo (World Bank deja huecos en sus
-- series). El landing en econ_raw las conserva por fidelidad; la limpieza es
-- trabajo de dbt. Materializado como view (siempre fresco, barato).

with source as (

    select * from {{ source('econ_raw', 'wb_observations') }}

),

cleaned as (

    select
        upper(trim(country_iso3))   as country_iso3,
        nullif(trim(country_name), '') as country_name,
        trim(indicator_code)        as indicator_code,
        nullif(trim(indicator_name), '') as indicator_name,
        anio::int                   as anio,
        valor::numeric              as valor
    from source
    where valor is not null
      and anio is not null
      and country_iso3 is not null

)

select * from cleaned

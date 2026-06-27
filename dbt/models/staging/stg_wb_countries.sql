-- Staging del catálogo de países: normaliza texto desde el landing crudo.
-- Enriquece dim_country con región, nivel de ingreso y geo. La región ya viene
-- normalizada desde Python, pero se aplica trim de nuevo por robustez.
-- Materializado como view.

with source as (

    select * from {{ source('econ_raw', 'wb_countries') }}

),

cleaned as (

    select
        upper(trim(country_iso3))   as country_iso3,
        upper(trim(iso2))           as iso2,
        nullif(trim(name), '')      as country_name,
        nullif(trim(region), '')    as region,
        nullif(trim(income_level), '') as income_level,
        nullif(trim(capital), '')   as capital,
        longitude::numeric          as longitude,
        latitude::numeric           as latitude
    from source
    where country_iso3 is not null

)

select * from cleaned

-- Tabla de hechos: grano país × indicador × año. Una observación real por fila
-- (los nulos ya se filtraron en staging). Lleva una surrogate key estable y FKs
-- a las dimensiones (validadas con relationships en _marts.yml).

with observations as (

    select * from {{ ref('stg_wb_observations') }}

)

select
    {{ dbt_utils.generate_surrogate_key(['country_iso3', 'indicator_code', 'anio']) }}
        as indicator_key,
    country_iso3,
    indicator_code,
    anio,
    valor
from observations

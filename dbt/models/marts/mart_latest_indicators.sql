-- Último valor disponible por país × indicador. Permite que el API responda
-- rápido "el dato más reciente" sin escanear toda la serie. Lo lee GET /latest.

with ranked as (

    select
        country_iso3,
        indicator_code,
        anio,
        valor,
        row_number() over (
            partition by country_iso3, indicator_code
            order by anio desc
        ) as rn
    from {{ ref('fct_indicators') }}

)

select
    country_iso3,
    indicator_code,
    anio,
    valor
from ranked
where rn = 1

-- Dimensión indicador: un registro por código de indicador. Combina el nombre
-- observado en los datos con la metadata curada del seed (unidad, categoría,
-- descripción en español).

with observed as (

    select
        indicator_code,
        max(indicator_name) as indicator_name
    from {{ ref('stg_wb_observations') }}
    group by indicator_code

),

metadata as (

    select * from {{ ref('indicator_metadata') }}

)

select
    observed.indicator_code,
    observed.indicator_name,
    metadata.unit,
    metadata.category,
    metadata.description_es
from observed
left join metadata using (indicator_code)

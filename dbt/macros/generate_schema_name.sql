{#
    Fuerza que TODOS los modelos, seeds y snapshots se materialicen en un único
    esquema: el `schema` del target (= `econ`).

    Comportamiento por defecto de dbt: si un modelo declara un esquema custom
    (vía +schema), dbt lo concatena -> `econ_staging`, `econ_marts`, etc. En esta
    instancia Supabase COMPARTIDA queremos un namespace limpio y ordenado, así que
    ignoramos el sufijo custom y devolvemos siempre `target.schema`.

    Decisión documentada en el README ("Design decisions").
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ target.schema | trim }}
{%- endmacro %}

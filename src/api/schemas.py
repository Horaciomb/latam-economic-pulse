"""Modelos pydantic de respuesta del API (tipan Swagger / OpenAPI)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthOut(BaseModel):
    """Estado del API y de la conexión a la base."""

    status: str = Field(examples=["ok"])
    database: str = Field(examples=["connected"])


class IndicatorOut(BaseModel):
    """Un indicador del catálogo (de dim_indicator)."""

    indicator_code: str = Field(examples=["NY.GDP.MKTP.CD"])
    indicator_name: str | None = Field(default=None, examples=["GDP (current US$)"])
    unit: str | None = Field(default=None, examples=["US$ corrientes"])
    category: str | None = Field(default=None, examples=["Cuentas nacionales"])
    description_es: str | None = None


class CountryOut(BaseModel):
    """Un país del catálogo (de dim_country)."""

    country_iso3: str = Field(examples=["BOL"])
    country_name: str | None = Field(default=None, examples=["Bolivia"])
    iso2: str | None = Field(default=None, examples=["BO"])
    region: str | None = Field(default=None, examples=["Latin America & Caribbean"])
    income_level: str | None = Field(default=None, examples=["Lower middle income"])
    capital: str | None = Field(default=None, examples=["La Paz"])
    longitude: float | None = None
    latitude: float | None = None


class ObservationOut(BaseModel):
    """Una observación de la serie temporal (de fct_indicators)."""

    country_iso3: str = Field(examples=["BOL"])
    indicator_code: str = Field(examples=["NY.GDP.MKTP.CD"])
    anio: int = Field(examples=[2023])
    valor: float | None = Field(default=None, examples=[52340206946.45])


class LatestOut(BaseModel):
    """Último valor de un indicador para un país (de mart_latest_indicators)."""

    country_iso3: str = Field(examples=["PER"])
    indicator_code: str = Field(examples=["FP.CPI.TOTL.ZG"])
    anio: int = Field(examples=[2023])
    valor: float | None = Field(default=None, examples=[3.24])


class StatsOut(BaseModel):
    """Estadísticos de un indicador en la región (min/max/promedio)."""

    indicator_code: str = Field(examples=["NY.GDP.MKTP.CD"])
    anio: int | None = Field(default=None, examples=[2023], description="Año analizado.")
    count: int = Field(examples=[33], description="Número de países con dato.")
    min_valor: float | None = None
    max_valor: float | None = None
    avg_valor: float | None = None

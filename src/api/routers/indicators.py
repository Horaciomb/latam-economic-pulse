"""Endpoints de indicadores, países, series y comparativas. Sólo delegan a services."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.api import services
from src.api.schemas import CountryOut, IndicatorOut, LatestOut, ObservationOut

router = APIRouter(tags=["indicators"])


@router.get("/indicators", response_model=list[IndicatorOut])
def get_indicators() -> list[dict]:
    """Catálogo de indicadores disponibles."""
    return services.list_indicators()


@router.get("/countries", response_model=list[CountryOut])
def get_countries() -> list[dict]:
    """Catálogo de países disponibles."""
    return services.list_countries()


@router.get("/indicators/{iso3}", response_model=list[ObservationOut])
def get_country_indicators(iso3: str) -> list[dict]:
    """Serie temporal de todos los indicadores de un país."""
    rows = services.get_country_series(iso3)
    if not rows:
        raise HTTPException(status_code=404, detail=f"Sin datos para el país '{iso3}'.")
    return rows


@router.get("/indicators/{iso3}/{indicator_code}", response_model=list[ObservationOut])
def get_country_indicator(iso3: str, indicator_code: str) -> list[dict]:
    """Serie temporal de un indicador para un país."""
    rows = services.get_country_indicator_series(iso3, indicator_code)
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"Sin datos para '{indicator_code}' en el país '{iso3}'.",
        )
    return rows


@router.get("/latest", response_model=list[LatestOut])
def get_latest(
    indicator: str = Query(..., description="Código del indicador, ej. FP.CPI.TOTL.ZG"),
) -> list[dict]:
    """Último valor de un indicador en todos los países (ranking)."""
    rows = services.get_latest_by_indicator(indicator)
    if not rows:
        raise HTTPException(status_code=404, detail=f"Sin datos para '{indicator}'.")
    return rows


@router.get("/compare", response_model=list[ObservationOut])
def compare(
    countries: str = Query(
        ..., description="Códigos ISO3 separados por ';', ej. BOL;PER;BRA"
    ),
    indicator: str = Query(..., description="Código del indicador a comparar"),
) -> list[dict]:
    """Comparativa de un indicador entre varios países."""
    iso3_codes = [c for c in countries.split(";") if c.strip()]
    if not iso3_codes:
        raise HTTPException(status_code=400, detail="Indica al menos un país.")
    rows = services.compare_countries(iso3_codes, indicator)
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"Sin datos para '{indicator}' en los países indicados.",
        )
    return rows

"""Endpoint de estadísticos agregados de un indicador. Sólo delega a services."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.api import services
from src.api.schemas import StatsOut

router = APIRouter(tags=["stats"])


@router.get("/stats/{indicator_code}", response_model=StatsOut)
def get_stats(indicator_code: str) -> dict:
    """Estadísticos (min/max/promedio) del indicador en la región.

    Calculado sobre el último valor disponible de cada país.
    """
    stats = services.get_indicator_stats(indicator_code)
    if stats is None:
        raise HTTPException(
            status_code=404, detail=f"Sin datos para '{indicator_code}'."
        )
    return stats

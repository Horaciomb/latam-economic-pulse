"""Aplicación FastAPI de Latam Economic Pulse.

Expone los datos limpios de los marts dbt. Sólo lectura. El pipeline EL (Python)
y la transformación (dbt) son procesos aparte; el API únicamente sirve.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.database import close_pool, init_pool, ping
from src.api.routers import indicators, stats
from src.api.schemas import HealthOut


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa el pool al arrancar y lo cierra al apagar."""
    init_pool()
    yield
    close_pool()


app = FastAPI(
    title="Latam Economic Pulse API",
    description=(
        "Indicadores económicos de Latinoamérica (World Bank) transformados con "
        "dbt y servidos sobre un modelo dimensional."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(indicators.router)
app.include_router(stats.router)


@app.get("/", tags=["meta"])
def root() -> dict:
    """Información del API y enlaces a la documentación."""
    return {
        "name": "Latam Economic Pulse API",
        "docs": "/docs",
        "dbt_docs": os.environ.get("DBT_DOCS_URL", "(configurar DBT_DOCS_URL)"),
        "source": "World Bank Indicators API v2",
    }


@app.get("/health", response_model=HealthOut, tags=["meta"])
def health() -> HealthOut:
    """Estado del API y de la conexión a la base."""
    try:
        connected = ping()
    except Exception:
        connected = False
    return HealthOut(
        status="ok",
        database="connected" if connected else "disconnected",
    )

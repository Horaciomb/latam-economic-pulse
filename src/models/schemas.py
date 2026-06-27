"""Modelos pydantic v2 que validan y aplanan la respuesta de la World Bank API.

La World Bank API v2 devuelve, en cada llamada, un array de DOS elementos:
``[metadata, [datos]]``. El primer elemento trae la paginación; el segundo, la
lista de registros (que puede ser ``None`` si no hay datos).

Estos modelos sólo validan la EXTRACCIÓN cruda. La limpieza de negocio (descartar
valores nulos, normalizar tipos en SQL, etc.) es responsabilidad de dbt, NO de
Python. Por eso ``WBObservation.valor`` admite ``None``: se landea todo crudo.
"""

from __future__ import annotations

from pydantic import BaseModel, field_validator


class WBPageMeta(BaseModel):
    """Metadatos de paginación (primer elemento del array de respuesta).

    Attributes:
        page: Número de página actual (1-indexed).
        pages: Total de páginas disponibles para la consulta.
        per_page: Tamaño de página solicitado.
        total: Total de registros que matchean la consulta.
    """

    page: int
    pages: int
    per_page: int
    total: int

    @field_validator("page", "pages", "per_page", "total", mode="before")
    @classmethod
    def _coerce_int(cls, value: object) -> int:
        """La API envía ``per_page`` como string en algunos endpoints."""
        return int(value)  # type: ignore[arg-type]


class WBObservation(BaseModel):
    """Una observación de un indicador (segundo elemento, lista de datos).

    Aplana el JSON anidado de la API a las columnas de ``econ_raw.wb_observations``.
    El ``value`` puede venir ``null`` cuando World Bank no tiene dato para ese
    país/año; se conserva como ``None`` (el filtrado lo hace dbt en staging).

    Attributes:
        country_iso3: Código ISO3 del país (de ``countryiso3code``, p. ej. 'BOL').
        country_name: Nombre del país (de ``country.value``).
        indicator_code: Código del indicador (de ``indicator.id``, p. ej.
            'NY.GDP.MKTP.CD').
        indicator_name: Nombre legible del indicador (de ``indicator.value``).
        anio: Año de la observación (de ``date``, casteado a int).
        valor: Valor numérico de la observación; ``None`` si no hay dato.
    """

    country_iso3: str
    country_name: str | None = None
    indicator_code: str
    indicator_name: str | None = None
    anio: int
    valor: float | None = None

    @classmethod
    def from_api(cls, raw: dict) -> WBObservation:
        """Construye una observación desde un registro crudo de la API.

        Args:
            raw: Dict de una observación tal como la entrega la API, con las
                claves anidadas ``indicator``, ``country``, ``countryiso3code``,
                ``date`` y ``value``.

        Returns:
            La observación validada y aplanada.
        """
        indicator = raw.get("indicator") or {}
        country = raw.get("country") or {}
        return cls(
            country_iso3=raw["countryiso3code"],
            country_name=country.get("value"),
            indicator_code=indicator["id"],
            indicator_name=indicator.get("value"),
            anio=int(raw["date"]),
            valor=raw.get("value"),
        )


class WBCountry(BaseModel):
    """Un país de la región LCN (Latin America & Caribbean).

    Aplana el JSON del endpoint ``/country?region=LCN`` a las columnas de
    ``econ_raw.wb_countries``. Enriquece ``dim_country`` con región, nivel de
    ingreso y coordenadas.

    Attributes:
        country_iso3: Código ISO3 (de ``id``, p. ej. 'BOL').
        iso2: Código ISO2 (de ``iso2Code``).
        name: Nombre del país.
        region: Región normalizada (la API la envía con espacio final → ``trim``).
        income_level: Nivel de ingreso (de ``incomeLevel.value``).
        capital: Ciudad capital (de ``capitalCity``); ``None`` si viene vacía.
        longitude: Longitud; ``None`` si viene vacía.
        latitude: Latitud; ``None`` si viene vacía.
    """

    country_iso3: str
    iso2: str | None = None
    name: str | None = None
    region: str | None = None
    income_level: str | None = None
    capital: str | None = None
    longitude: float | None = None
    latitude: float | None = None

    @field_validator("region", "income_level", "capital", "name", "iso2", mode="before")
    @classmethod
    def _strip_text(cls, value: object) -> str | None:
        """Normaliza texto: ``trim`` y convierte cadenas vacías en ``None``.

        La API entrega ``region.value`` con un espacio final y ``capitalCity``
        como cadena vacía cuando no aplica.
        """
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator("longitude", "latitude", mode="before")
    @classmethod
    def _empty_to_none(cls, value: object) -> float | None:
        """La API envía longitud/latitud como string, vacío si no hay dato."""
        if value is None or value == "":
            return None
        return float(value)  # type: ignore[arg-type]

    @classmethod
    def from_api(cls, raw: dict) -> WBCountry:
        """Construye un país desde un registro crudo de la API ``/country``.

        Args:
            raw: Dict de un país con las claves ``id``, ``iso2Code``, ``name``,
                ``region``, ``incomeLevel``, ``capitalCity``, ``longitude`` y
                ``latitude``.

        Returns:
            El país validado y aplanado.
        """
        region = raw.get("region") or {}
        income = raw.get("incomeLevel") or {}
        return cls(
            country_iso3=raw["id"],
            iso2=raw.get("iso2Code"),
            name=raw.get("name"),
            region=region.get("value"),
            income_level=income.get("value"),
            capital=raw.get("capitalCity"),
            longitude=raw.get("longitude"),
            latitude=raw.get("latitude"),
        )

    @property
    def is_aggregate(self) -> bool:
        """``True`` si el registro es un agregado regional, no un país real.

        El filtro ``region=LCN`` ya los excluye, pero esto sirve de guarda
        defensiva (los agregados traen ``region.value == 'Aggregates'``).
        """
        return self.region == "Aggregates"

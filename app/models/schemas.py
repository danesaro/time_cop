"""Pydantic models for request/response validation and data transfer."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ── Gemini AI ────────────────────────────────────────────────────────────────

class ActividadGemini(BaseModel):
    """A single activity parsed by Gemini from the user's natural-language input."""

    descripcion: str = Field(..., min_length=1, description="Professional activity description")
    proyecto: str = Field(..., min_length=1, description="Associated project name")
    categoria: str = Field(
        ...,
        pattern=r"^(proyectoFacturable|proyectoNoFacturable|otrosNoFacturable)$",
        description="Activity category",
    )
    horas_estimadas: Decimal = Field(..., gt=0, le=24, description="Estimated hours")


class RespuestaGemini(BaseModel):
    """Wrapper for the full Gemini JSON response."""

    actividades: list[ActividadGemini] = Field(..., min_length=1)


# ── Database records ─────────────────────────────────────────────────────────

class RegistroTiempoCreate(BaseModel):
    """Data needed to insert a time record."""

    fecha: date
    usuario_telegram_id: int
    descripcion: str
    proyecto: str
    categoria: str
    horas_estimadas: Decimal
    texto_original: Optional[str] = None


class RegistroTiempoResponse(BaseModel):
    """A time record as returned from the database."""

    id: UUID
    fecha: date
    usuario_telegram_id: int
    descripcion: str
    proyecto: str
    categoria: str
    horas_estimadas: Decimal
    texto_original: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ── Reports ──────────────────────────────────────────────────────────────────

class ReportRow(BaseModel):
    """A single row in the XLSX report."""

    fecha: date
    proyecto: str
    descripcion: str
    categoria: str
    horas: Decimal

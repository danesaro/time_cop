"""Utility helpers for timezone operations, date parsing, and message formatting."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

import pytz

from app.config import get_settings
from app.models.schemas import ActividadGemini


def get_timezone() -> pytz.BaseTzInfo:
    """Return the configured application timezone."""
    return pytz.timezone(get_settings().TIMEZONE)


def fecha_colombia_hoy() -> date:
    """Return today's date in the configured timezone (default: America/Bogota)."""
    tz = get_timezone()
    return datetime.now(tz).date()


def ahora_colombia() -> datetime:
    """Return the current datetime in the configured timezone."""
    tz = get_timezone()
    return datetime.now(tz)


def parsear_fecha(texto: str) -> Optional[date]:
    """Parse a date string in common formats.

    Supported formats:
        - YYYY-MM-DD
        - DD/MM/YYYY
        - DD-MM-YYYY

    Args:
        texto: The date string to parse.

    Returns:
        A date object, or None if parsing fails.
    """
    texto = texto.strip()
    formatos = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]
    for fmt in formatos:
        try:
            return datetime.strptime(texto, fmt).date()
        except ValueError:
            continue
    return None


def inicio_semana(fecha: date) -> date:
    """Return the Monday of the week containing *fecha*."""
    return fecha - timedelta(days=fecha.weekday())


def fin_semana(fecha: date) -> date:
    """Return the Sunday of the week containing *fecha*."""
    return fecha + timedelta(days=6 - fecha.weekday())


def formatear_resumen(actividades: list[ActividadGemini], fecha: date) -> str:
    """Build a nicely formatted Telegram summary message for recorded activities.

    Args:
        actividades: The list of activities processed by Gemini.
        fecha: The date for which activities were recorded.

    Returns:
        A multi-line string ready to send via Telegram.
    """
    total_horas = sum(a.horas_estimadas for a in actividades)
    cantidad = len(actividades)

    lineas: list[str] = [
        f"✅ Registrado exitosamente el {fecha.isoformat()}",
        "",
        f"📝 {cantidad} actividad(es) guardada(s):",
        "",
    ]

    for i, act in enumerate(actividades, 1):
        emoji_cat = _emoji_categoria(act.categoria)
        lineas.append(f"{i}. 📁 {act.proyecto}")
        lineas.append(f"   {act.descripcion}")
        lineas.append(f"   ⏱️ {act.horas_estimadas}h — {emoji_cat}{act.categoria}")
        lineas.append("")

    lineas.append(f"⏰ Total: {total_horas} horas")
    return "\n".join(lineas)


def formatear_registros(registros: list[dict], fecha: date) -> str:
    """Build a summary of existing records for a given date.

    Args:
        registros: List of record dicts from the database.
        fecha: The date being queried.

    Returns:
        A formatted message string.
    """
    if not registros:
        return f"📭 No hay registros para el {fecha.isoformat()}"

    total_horas = sum(Decimal(str(r["horas_estimadas"])) for r in registros)
    lineas: list[str] = [
        f"📋 Registros del {fecha.isoformat()}",
        f"📝 {len(registros)} actividad(es):",
        "",
    ]

    for i, r in enumerate(registros, 1):
        emoji_cat = _emoji_categoria(r["categoria"])
        lineas.append(f"{i}. 📁 {r['proyecto']}")
        lineas.append(f"   {r['descripcion']}")
        lineas.append(f"   ⏱️ {r['horas_estimadas']}h — {emoji_cat}{r['categoria']}")
        lineas.append(f"   🆔 {str(r['id'])[:8]}...")
        lineas.append("")

    lineas.append(f"⏰ Total: {total_horas} horas")
    return "\n".join(lineas)


def formatear_resumen_semana(registros: list[dict], fecha_inicio: date, fecha_fin: date) -> str:
    """Build a weekly summary grouped by date.

    Args:
        registros: List of record dicts from the database.
        fecha_inicio: Monday of the week.
        fecha_fin: Sunday of the week.

    Returns:
        A formatted weekly summary string.
    """
    if not registros:
        return f"📭 No hay registros para la semana del {fecha_inicio.isoformat()} al {fecha_fin.isoformat()}"

    # Group by date
    por_fecha: dict[date, list[dict]] = {}
    for r in registros:
        f = r["fecha"] if isinstance(r["fecha"], date) else date.fromisoformat(str(r["fecha"]))
        por_fecha.setdefault(f, []).append(r)

    total_general = Decimal("0")
    lineas: list[str] = [
        f"📊 Resumen semanal ({fecha_inicio.isoformat()} → {fecha_fin.isoformat()})",
        "",
    ]

    for f in sorted(por_fecha.keys()):
        regs = por_fecha[f]
        horas_dia = sum(Decimal(str(r["horas_estimadas"])) for r in regs)
        total_general += horas_dia
        lineas.append(f"📅 {f.isoformat()} — {horas_dia}h ({len(regs)} actividades)")
        for r in regs:
            lineas.append(f"   • {r['proyecto']}: {r['descripcion']} ({r['horas_estimadas']}h)")
        lineas.append("")

    lineas.append(f"⏰ Total semana: {total_general} horas")
    return "\n".join(lineas)


def _emoji_categoria(categoria: str) -> str:
    """Return an emoji prefix for the given category."""
    return {
        "proyectoFacturable": "💰 ",
        "proyectoNoFacturable": "📌 ",
        "otrosNoFacturable": "📎 ",
    }.get(categoria, "")

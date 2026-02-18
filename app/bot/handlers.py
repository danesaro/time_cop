"""Simple command handlers and error handler for the Telegram bot."""

import logging

from telegram import BotCommand, Update
from telegram.ext import ContextTypes

from app.models.database import get_pool
from app.services import db_service
from app.utils import (
    fecha_colombia_hoy,
    formatear_resumen_semana,
    inicio_semana,
    fin_semana,
)

logger = logging.getLogger(__name__)


# ── /start ───────────────────────────────────────────────────────────────────

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start — welcome message with available commands."""
    nombre = update.effective_user.first_name or "Usuario"
    await update.message.reply_text(
        f"👋 ¡Hola, {nombre}! Soy *Time Cop* 🕐\n\n"
        "Te ayudo a registrar tus horas de trabajo de forma rápida y fácil "
        "usando inteligencia artificial.\n\n"
        "📌 *Comandos disponibles:*\n\n"
        "▸ /registrar\\_dia\\_actual — Registrar actividades de hoy\n"
        "▸ /registrar\\_otro\\_dia — Registrar un día anterior\n"
        "▸ /recuperar\\_registro\\_por\\_fecha — Ver registros de una fecha\n"
        "▸ /ver\\_semana — Resumen semanal\n"
        "▸ /generar\\_reporte — Generar reporte XLSX del mes\n"
        "▸ /eliminar\\_registro — Eliminar un registro\n\n"
        "💡 _Simplemente describe tus actividades en lenguaje natural y yo me "
        "encargo de estructurarlas._",
        parse_mode="Markdown",
    )


# ── /ver_semana ──────────────────────────────────────────────────────────────

async def ver_semana_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /ver_semana — show weekly summary."""
    telegram_id = update.effective_user.id
    hoy = fecha_colombia_hoy()
    lunes = inicio_semana(hoy)
    domingo = fin_semana(hoy)

    pool = get_pool()
    registros = await db_service.obtener_registros_semana(pool, telegram_id, lunes, domingo)
    resumen = formatear_resumen_semana(registros, lunes, domingo)
    await update.message.reply_text(resumen)


# ── Error handler ────────────────────────────────────────────────────────────

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log unhandled exceptions and notify the user if possible."""
    logger.error("Unhandled exception: %s", context.error, exc_info=context.error)

    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "❌ Ocurrió un error inesperado. Por favor intenta de nuevo más tarde."
            )
        except Exception:
            logger.error("Failed to send error message to user")


# ── Bot commands menu ────────────────────────────────────────────────────────

BOT_COMMANDS = [
    BotCommand("start", "Inicio y ayuda"),
    BotCommand("registrar_dia_actual", "Registrar actividades de hoy"),
    BotCommand("registrar_otro_dia", "Registrar un día anterior"),
    BotCommand("recuperar_registro_por_fecha", "Ver registros de una fecha"),
    BotCommand("ver_semana", "Resumen semanal"),
    BotCommand("generar_reporte", "Generar reporte XLSX del mes"),
    BotCommand("eliminar_registro", "Eliminar un registro"),
]

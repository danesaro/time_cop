"""Conversation handlers for multi-step Telegram bot flows."""

import logging
from uuid import UUID

from telegram import Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from app.bot.states import (
    CONVERSATION_TIMEOUT,
    ESPERANDO_ACTIVIDADES,
    ESPERANDO_ACTIVIDADES_OTRO_DIA,
    ESPERANDO_FECHA,
    ESPERANDO_FECHA_CONSULTA,
    ESPERANDO_FECHA_ELIMINAR,
    ESPERANDO_MES_REPORTE,
    ESPERANDO_SELECCION_ELIMINAR,
)
from app.models.database import get_pool
from app.services import db_service, gemini_service
from app.services.gemini_service import GeminiProcessingError
from app.services.sheets_service import generar_reporte_xlsx
from app.utils import (
    fecha_colombia_hoy,
    formatear_registros,
    formatear_resumen,
    parsear_fecha,
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# REGISTRAR DÍA ACTUAL
# ══════════════════════════════════════════════════════════════════════════════

async def registrar_dia_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for /registrar_dia_actual — ask user what they did today."""
    await update.message.reply_text(
        "📝 ¿Qué tanto hiciste hoy?\n\n"
        "Descríbeme tus actividades de forma natural. Por ejemplo:\n"
        "_\"Hoy tuve reunión de planning 2h, revisé PRs del proyecto Alpha 1.5h, "
        "documenté la API 3h, y tuve la daily 0.5h\"_",
        parse_mode="Markdown",
    )
    return ESPERANDO_ACTIVIDADES


async def procesar_actividades_hoy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process user text with Gemini and save records for today."""
    texto = update.message.text
    telegram_id = update.effective_user.id
    fecha = fecha_colombia_hoy()

    await update.message.reply_text("⏳ Procesando tus actividades con IA...")

    try:
        actividades = await gemini_service.procesar_actividades(texto)
    except GeminiProcessingError as exc:
        logger.error("Gemini processing failed for user %d: %s", telegram_id, exc)
        await update.message.reply_text(
            "❌ No pude procesar las actividades. Por favor intenta de nuevo "
            "con una descripción más clara.\n\n"
            f"Error: {exc}"
        )
        return ConversationHandler.END

    pool = get_pool()
    actividades_dicts = [a.model_dump() for a in actividades]

    try:
        await db_service.crear_registros(pool, telegram_id, fecha, actividades_dicts, texto)
    except Exception as exc:
        logger.error("DB insert failed for user %d: %s", telegram_id, exc)
        await update.message.reply_text("❌ Error al guardar en la base de datos. Intenta de nuevo más tarde.")
        return ConversationHandler.END

    resumen = formatear_resumen(actividades, fecha)
    await update.message.reply_text(resumen)
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════════════════════════
# REGISTRAR OTRO DÍA
# ══════════════════════════════════════════════════════════════════════════════

async def registrar_otro_dia_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for /registrar_otro_dia — ask for target date."""
    await update.message.reply_text(
        "📅 ¿Para qué fecha deseas registrar actividades?\n\n"
        "Envía la fecha en formato: `YYYY-MM-DD`, `DD/MM/YYYY` o `DD-MM-YYYY`",
        parse_mode="Markdown",
    )
    return ESPERANDO_FECHA


async def recibir_fecha_otro_dia(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Parse the date and ask for activities."""
    fecha = parsear_fecha(update.message.text)
    if fecha is None:
        await update.message.reply_text(
            "❌ Fecha inválida. Usa formato `YYYY-MM-DD`, `DD/MM/YYYY` o `DD-MM-YYYY`.\n"
            "Intenta de nuevo o envía /cancelar",
            parse_mode="Markdown",
        )
        return ESPERANDO_FECHA

    context.user_data["fecha_registro"] = fecha
    await update.message.reply_text(
        f"📝 Registrando para el {fecha.isoformat()}.\n\n¿Qué actividades realizaste ese día?"
    )
    return ESPERANDO_ACTIVIDADES_OTRO_DIA


async def procesar_actividades_otro_dia(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process user text with Gemini and save records for the chosen date."""
    texto = update.message.text
    telegram_id = update.effective_user.id
    fecha = context.user_data.get("fecha_registro", fecha_colombia_hoy())

    await update.message.reply_text("⏳ Procesando tus actividades con IA...")

    try:
        actividades = await gemini_service.procesar_actividades(texto)
    except GeminiProcessingError as exc:
        logger.error("Gemini processing failed for user %d: %s", telegram_id, exc)
        await update.message.reply_text(f"❌ No pude procesar las actividades.\n\nError: {exc}")
        return ConversationHandler.END

    pool = get_pool()
    actividades_dicts = [a.model_dump() for a in actividades]

    try:
        await db_service.crear_registros(pool, telegram_id, fecha, actividades_dicts, texto)
    except Exception as exc:
        logger.error("DB insert failed for user %d: %s", telegram_id, exc)
        await update.message.reply_text("❌ Error al guardar en la base de datos.")
        return ConversationHandler.END

    resumen = formatear_resumen(actividades, fecha)
    await update.message.reply_text(resumen)

    context.user_data.pop("fecha_registro", None)
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════════════════════════
# ELIMINAR REGISTRO
# ══════════════════════════════════════════════════════════════════════════════

async def eliminar_registro_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for /eliminar_registro — ask for the date."""
    await update.message.reply_text(
        "🗑️ ¿De qué fecha deseas eliminar un registro?\n\n"
        "Envía la fecha en formato: `YYYY-MM-DD`, `DD/MM/YYYY` o `DD-MM-YYYY`",
        parse_mode="Markdown",
    )
    return ESPERANDO_FECHA_ELIMINAR


async def mostrar_registros_eliminar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show records for the chosen date and ask which to delete."""
    fecha = parsear_fecha(update.message.text)
    if fecha is None:
        await update.message.reply_text(
            "❌ Fecha inválida. Intenta de nuevo o envía /cancelar"
        )
        return ESPERANDO_FECHA_ELIMINAR

    telegram_id = update.effective_user.id
    pool = get_pool()
    registros = await db_service.obtener_registros_por_fecha(pool, telegram_id, fecha)

    if not registros:
        await update.message.reply_text(f"📭 No hay registros para el {fecha.isoformat()}")
        return ConversationHandler.END

    context.user_data["registros_eliminar"] = registros

    resumen = formatear_registros(registros, fecha)
    await update.message.reply_text(
        f"{resumen}\n\n"
        "🗑️ Envía el número del registro que deseas eliminar, o /cancelar para salir."
    )
    return ESPERANDO_SELECCION_ELIMINAR


async def confirmar_eliminacion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Delete the selected record."""
    registros = context.user_data.get("registros_eliminar", [])

    try:
        seleccion = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Envía solo el número del registro. Intenta de nuevo o /cancelar")
        return ESPERANDO_SELECCION_ELIMINAR

    if seleccion < 1 or seleccion > len(registros):
        await update.message.reply_text(
            f"❌ Número inválido. Elige entre 1 y {len(registros)}, o /cancelar"
        )
        return ESPERANDO_SELECCION_ELIMINAR

    registro = registros[seleccion - 1]
    telegram_id = update.effective_user.id
    pool = get_pool()

    deleted = await db_service.eliminar_registro(pool, UUID(str(registro["id"])), telegram_id)

    if deleted:
        await update.message.reply_text(
            f"✅ Registro eliminado:\n"
            f"📁 {registro['proyecto']} — {registro['descripcion']}"
        )
    else:
        await update.message.reply_text("❌ No se pudo eliminar el registro.")

    context.user_data.pop("registros_eliminar", None)
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════════════════════════
# RECUPERAR REGISTRO POR FECHA
# ══════════════════════════════════════════════════════════════════════════════

async def recuperar_registro_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for /recuperar_registro_por_fecha — ask for the date."""
    await update.message.reply_text(
        "📅 ¿De qué fecha deseas consultar los registros?\n\n"
        "Envía la fecha en formato: `YYYY-MM-DD`, `DD/MM/YYYY` o `DD-MM-YYYY`",
        parse_mode="Markdown",
    )
    return ESPERANDO_FECHA_CONSULTA


async def mostrar_registros_fecha(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show records for the chosen date."""
    fecha = parsear_fecha(update.message.text)
    if fecha is None:
        await update.message.reply_text("❌ Fecha inválida. Intenta de nuevo o /cancelar")
        return ESPERANDO_FECHA_CONSULTA

    telegram_id = update.effective_user.id
    pool = get_pool()
    registros = await db_service.obtener_registros_por_fecha(pool, telegram_id, fecha)
    resumen = formatear_registros(registros, fecha)
    await update.message.reply_text(resumen)
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════════════════════════
# GENERAR REPORTE
# ══════════════════════════════════════════════════════════════════════════════

async def generar_reporte_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for /generar_reporte — ask for the month."""
    hoy = fecha_colombia_hoy()
    await update.message.reply_text(
        "📊 ¿Para qué mes deseas generar el reporte?\n\n"
        f"Envía el mes en formato `MM/YYYY` (ejemplo: `{hoy.month:02d}/{hoy.year}`)",
        parse_mode="Markdown",
    )
    return ESPERANDO_MES_REPORTE


async def procesar_reporte(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Generate and send the XLSX report."""
    texto = update.message.text.strip()

    # Parse MM/YYYY
    try:
        partes = texto.split("/")
        mes = int(partes[0])
        año = int(partes[1])
        if not (1 <= mes <= 12) or año < 2020:
            raise ValueError("Invalid month/year")
    except (ValueError, IndexError):
        await update.message.reply_text(
            "❌ Formato inválido. Envía `MM/YYYY` (ejemplo: `02/2026`). Intenta de nuevo o /cancelar",
            parse_mode="Markdown",
        )
        return ESPERANDO_MES_REPORTE

    telegram_id = update.effective_user.id
    pool = get_pool()

    await update.message.reply_text("⏳ Generando reporte...")

    registros = await db_service.obtener_registros_mes(pool, telegram_id, año, mes)

    if not registros:
        await update.message.reply_text(f"📭 No hay registros para {mes:02d}/{año}")
        return ConversationHandler.END

    nombre_usuario = update.effective_user.full_name
    buffer = generar_reporte_xlsx(registros, mes, año, nombre_usuario)

    meses_es = [
        "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
    ]
    filename = f"reporte_{meses_es[mes]}_{año}.xlsx"

    await update.message.reply_document(
        document=buffer,
        filename=filename,
        caption=f"📊 Reporte de tiempos — {meses_es[mes]} {año}\n📝 {len(registros)} registros",
    )
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════════════════════════
# SHARED HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /cancelar in any conversation flow."""
    context.user_data.clear()
    await update.message.reply_text("❌ Operación cancelada.")
    return ConversationHandler.END


async def timeout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle conversation timeout."""
    if update and update.effective_user:
        logger.info("Conversation timed out for user %d", update.effective_user.id)
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════════════════════════
# BUILD CONVERSATION HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

def build_registrar_dia_handler() -> ConversationHandler:
    """Build the ConversationHandler for /registrar_dia_actual."""
    return ConversationHandler(
        entry_points=[CommandHandler("registrar_dia_actual", registrar_dia_cmd)],
        states={
            ESPERANDO_ACTIVIDADES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, procesar_actividades_hoy),
            ],
            ConversationHandler.TIMEOUT: [
                MessageHandler(filters.ALL, timeout),
            ],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
        conversation_timeout=CONVERSATION_TIMEOUT,
    )


def build_registrar_otro_dia_handler() -> ConversationHandler:
    """Build the ConversationHandler for /registrar_otro_dia."""
    return ConversationHandler(
        entry_points=[CommandHandler("registrar_otro_dia", registrar_otro_dia_cmd)],
        states={
            ESPERANDO_FECHA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_fecha_otro_dia),
            ],
            ESPERANDO_ACTIVIDADES_OTRO_DIA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, procesar_actividades_otro_dia),
            ],
            ConversationHandler.TIMEOUT: [
                MessageHandler(filters.ALL, timeout),
            ],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
        conversation_timeout=CONVERSATION_TIMEOUT,
    )


def build_eliminar_registro_handler() -> ConversationHandler:
    """Build the ConversationHandler for /eliminar_registro."""
    return ConversationHandler(
        entry_points=[CommandHandler("eliminar_registro", eliminar_registro_cmd)],
        states={
            ESPERANDO_FECHA_ELIMINAR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, mostrar_registros_eliminar),
            ],
            ESPERANDO_SELECCION_ELIMINAR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, confirmar_eliminacion),
            ],
            ConversationHandler.TIMEOUT: [
                MessageHandler(filters.ALL, timeout),
            ],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
        conversation_timeout=CONVERSATION_TIMEOUT,
    )


def build_recuperar_registro_handler() -> ConversationHandler:
    """Build the ConversationHandler for /recuperar_registro_por_fecha."""
    return ConversationHandler(
        entry_points=[CommandHandler("recuperar_registro_por_fecha", recuperar_registro_cmd)],
        states={
            ESPERANDO_FECHA_CONSULTA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, mostrar_registros_fecha),
            ],
            ConversationHandler.TIMEOUT: [
                MessageHandler(filters.ALL, timeout),
            ],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
        conversation_timeout=CONVERSATION_TIMEOUT,
    )


def build_generar_reporte_handler() -> ConversationHandler:
    """Build the ConversationHandler for /generar_reporte."""
    return ConversationHandler(
        entry_points=[CommandHandler("generar_reporte", generar_reporte_cmd)],
        states={
            ESPERANDO_MES_REPORTE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, procesar_reporte),
            ],
            ConversationHandler.TIMEOUT: [
                MessageHandler(filters.ALL, timeout),
            ],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
        conversation_timeout=CONVERSATION_TIMEOUT,
    )

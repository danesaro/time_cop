"""Conversation state constants for Telegram bot flows."""

# ── registrar_dia_actual ─────────────────────────────────────────────────────
ESPERANDO_ACTIVIDADES = 1

# ── registrar_otro_dia ───────────────────────────────────────────────────────
ESPERANDO_FECHA = 2
ESPERANDO_ACTIVIDADES_OTRO_DIA = 3

# ── eliminar_registro ────────────────────────────────────────────────────────
ESPERANDO_FECHA_ELIMINAR = 4
ESPERANDO_SELECCION_ELIMINAR = 5

# ── recuperar_registro_por_fecha ─────────────────────────────────────────────
ESPERANDO_FECHA_CONSULTA = 6

# ── generar_reporte ──────────────────────────────────────────────────────────
ESPERANDO_MES_REPORTE = 7

# ── Conversation timeout (seconds) ──────────────────────────────────────────
CONVERSATION_TIMEOUT = 600  # 10 minutes

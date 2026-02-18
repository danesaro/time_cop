"""Database service — raw SQL queries via asyncpg."""

import logging
from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

import asyncpg

logger = logging.getLogger(__name__)


# ── Time records ─────────────────────────────────────────────────────────────

async def crear_registros(
    pool: asyncpg.Pool,
    telegram_id: int,
    fecha: date,
    actividades: list[dict],
    texto_original: Optional[str] = None,
) -> list[dict]:
    """Insert multiple time records in a single transaction.

    Args:
        pool: asyncpg connection pool.
        telegram_id: Telegram user ID.
        fecha: Date for the records.
        actividades: List of activity dicts with keys: descripcion, proyecto, categoria, horas_estimadas.
        texto_original: Original user text (stored for auditing).

    Returns:
        List of inserted record dicts.
    """
    query = """
        INSERT INTO registros_tiempo (fecha, usuario_telegram_id, descripcion, proyecto, categoria, horas_estimadas, texto_original)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id, fecha, usuario_telegram_id, descripcion, proyecto, categoria, horas_estimadas, texto_original, created_at, updated_at
    """
    registros: list[dict] = []

    async with pool.acquire() as conn:
        async with conn.transaction():
            for act in actividades:
                row = await conn.fetchrow(
                    query,
                    fecha,
                    telegram_id,
                    act["descripcion"],
                    act["proyecto"],
                    act["categoria"],
                    Decimal(str(act["horas_estimadas"])),
                    texto_original,
                )
                registros.append(dict(row))

    logger.info(
        "Inserted %d records for user %d on %s",
        len(registros),
        telegram_id,
        fecha.isoformat(),
    )
    return registros


async def obtener_registros_por_fecha(
    pool: asyncpg.Pool,
    telegram_id: int,
    fecha: date,
) -> list[dict]:
    """Fetch all records for a user on a given date.

    Args:
        pool: asyncpg connection pool.
        telegram_id: Telegram user ID.
        fecha: Date to query.

    Returns:
        List of record dicts ordered by creation time.
    """
    query = """
        SELECT id, fecha, usuario_telegram_id, descripcion, proyecto, categoria, horas_estimadas, texto_original, created_at, updated_at
        FROM registros_tiempo
        WHERE usuario_telegram_id = $1 AND fecha = $2
        ORDER BY created_at ASC
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, telegram_id, fecha)
    return [dict(r) for r in rows]


async def obtener_registros_semana(
    pool: asyncpg.Pool,
    telegram_id: int,
    fecha_inicio: date,
    fecha_fin: date,
) -> list[dict]:
    """Fetch all records for a user within a date range (inclusive).

    Args:
        pool: asyncpg connection pool.
        telegram_id: Telegram user ID.
        fecha_inicio: Start date (Monday).
        fecha_fin: End date (Sunday).

    Returns:
        List of record dicts ordered by date and creation time.
    """
    query = """
        SELECT id, fecha, usuario_telegram_id, descripcion, proyecto, categoria, horas_estimadas, texto_original, created_at, updated_at
        FROM registros_tiempo
        WHERE usuario_telegram_id = $1 AND fecha BETWEEN $2 AND $3
        ORDER BY fecha ASC, created_at ASC
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, telegram_id, fecha_inicio, fecha_fin)
    return [dict(r) for r in rows]


async def obtener_registros_mes(
    pool: asyncpg.Pool,
    telegram_id: int,
    año: int,
    mes: int,
) -> list[dict]:
    """Fetch all records for a user in a specific month.

    Args:
        pool: asyncpg connection pool.
        telegram_id: Telegram user ID.
        año: Year.
        mes: Month number (1-12).

    Returns:
        List of record dicts ordered by date and creation time.
    """
    query = """
        SELECT id, fecha, usuario_telegram_id, descripcion, proyecto, categoria, horas_estimadas, texto_original, created_at, updated_at
        FROM registros_tiempo
        WHERE usuario_telegram_id = $1
          AND EXTRACT(YEAR FROM fecha) = $2
          AND EXTRACT(MONTH FROM fecha) = $3
        ORDER BY fecha ASC, created_at ASC
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, telegram_id, año, mes)
    return [dict(r) for r in rows]


async def eliminar_registro(
    pool: asyncpg.Pool,
    registro_id: UUID,
    telegram_id: int,
) -> bool:
    """Delete a time record if it belongs to the given user.

    Args:
        pool: asyncpg connection pool.
        registro_id: UUID of the record to delete.
        telegram_id: Telegram user ID (ownership check).

    Returns:
        True if a row was deleted, False otherwise.
    """
    query = """
        DELETE FROM registros_tiempo
        WHERE id = $1 AND usuario_telegram_id = $2
    """
    async with pool.acquire() as conn:
        result = await conn.execute(query, registro_id, telegram_id)

    deleted = result == "DELETE 1"
    if deleted:
        logger.info("Deleted record %s for user %d", registro_id, telegram_id)
    else:
        logger.warning("Record %s not found or not owned by user %d", registro_id, telegram_id)
    return deleted


# ── User state (conversation persistence) ───────────────────────────────────

async def guardar_estado(
    pool: asyncpg.Pool,
    telegram_id: int,
    estado: str,
    datos_temporales: Optional[dict] = None,
) -> None:
    """Upsert the conversation state for a user.

    Args:
        pool: asyncpg connection pool.
        telegram_id: Telegram user ID.
        estado: Current conversation state identifier.
        datos_temporales: Optional JSON-serialisable data to persist.
    """
    query = """
        INSERT INTO estados_usuarios (telegram_id, estado, datos_temporales, updated_at)
        VALUES ($1, $2, $3::jsonb, NOW())
        ON CONFLICT (telegram_id)
        DO UPDATE SET estado = $2, datos_temporales = $3::jsonb, updated_at = NOW()
    """
    import json
    datos_json = json.dumps(datos_temporales) if datos_temporales else None

    async with pool.acquire() as conn:
        await conn.execute(query, telegram_id, estado, datos_json)

    logger.debug("Saved state '%s' for user %d", estado, telegram_id)


async def obtener_estado(
    pool: asyncpg.Pool,
    telegram_id: int,
) -> Optional[dict]:
    """Get the conversation state for a user.

    Args:
        pool: asyncpg connection pool.
        telegram_id: Telegram user ID.

    Returns:
        Dict with 'estado' and 'datos_temporales', or None if no state exists.
    """
    query = """
        SELECT estado, datos_temporales
        FROM estados_usuarios
        WHERE telegram_id = $1
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, telegram_id)

    if row is None:
        return None
    return dict(row)


async def limpiar_estado(
    pool: asyncpg.Pool,
    telegram_id: int,
) -> None:
    """Clear the conversation state for a user.

    Args:
        pool: asyncpg connection pool.
        telegram_id: Telegram user ID.
    """
    query = "DELETE FROM estados_usuarios WHERE telegram_id = $1"
    async with pool.acquire() as conn:
        await conn.execute(query, telegram_id)
    logger.debug("Cleared state for user %d", telegram_id)

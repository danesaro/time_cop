"""Tests for the database service (mocked asyncpg pool)."""

import json
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services import db_service


def _mock_pool():
    """Create a mock asyncpg pool with acquire() context manager."""
    pool = MagicMock()
    conn = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx

    # Transaction context manager — must be a sync call returning an async CM
    tx_ctx = MagicMock()
    tx_ctx.__aenter__ = AsyncMock()
    tx_ctx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx_ctx)

    return pool, conn


class TestCrearRegistros:
    """Tests for bulk insert of time records."""

    @pytest.mark.asyncio
    async def test_inserts_multiple_records(self):
        pool, conn = _mock_pool()
        record_id = uuid4()

        conn.fetchrow = AsyncMock(return_value={
            "id": record_id,
            "fecha": date(2026, 2, 17),
            "usuario_telegram_id": 123,
            "descripcion": "Test",
            "proyecto": "P1",
            "categoria": "proyectoFacturable",
            "horas_estimadas": Decimal("2.00"),
            "texto_original": "raw text",
            "created_at": "2026-02-17T10:00:00",
            "updated_at": "2026-02-17T10:00:00",
        })

        actividades = [
            {"descripcion": "Task A", "proyecto": "P1", "categoria": "proyectoFacturable", "horas_estimadas": 2.0},
            {"descripcion": "Task B", "proyecto": "P2", "categoria": "proyectoNoFacturable", "horas_estimadas": 3.0},
        ]

        result = await db_service.crear_registros(pool, 123, date(2026, 2, 17), actividades, "raw text")
        assert len(result) == 2
        assert conn.fetchrow.call_count == 2


class TestObtenerRegistros:
    """Tests for record retrieval queries."""

    @pytest.mark.asyncio
    async def test_obtener_por_fecha(self):
        pool, conn = _mock_pool()
        conn.fetch = AsyncMock(return_value=[
            {"id": uuid4(), "fecha": date(2026, 2, 17), "descripcion": "T1"},
        ])

        result = await db_service.obtener_registros_por_fecha(pool, 123, date(2026, 2, 17))
        assert len(result) == 1
        conn.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_obtener_semana(self):
        pool, conn = _mock_pool()
        conn.fetch = AsyncMock(return_value=[])

        result = await db_service.obtener_registros_semana(pool, 123, date(2026, 2, 16), date(2026, 2, 22))
        assert result == []

    @pytest.mark.asyncio
    async def test_obtener_mes(self):
        pool, conn = _mock_pool()
        conn.fetch = AsyncMock(return_value=[])

        result = await db_service.obtener_registros_mes(pool, 123, 2026, 2)
        assert result == []


class TestEliminarRegistro:
    """Tests for record deletion."""

    @pytest.mark.asyncio
    async def test_delete_success(self):
        pool, conn = _mock_pool()
        conn.execute = AsyncMock(return_value="DELETE 1")

        result = await db_service.eliminar_registro(pool, uuid4(), 123)
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_not_found(self):
        pool, conn = _mock_pool()
        conn.execute = AsyncMock(return_value="DELETE 0")

        result = await db_service.eliminar_registro(pool, uuid4(), 123)
        assert result is False


class TestEstadoUsuario:
    """Tests for user state management."""

    @pytest.mark.asyncio
    async def test_guardar_estado(self):
        pool, conn = _mock_pool()
        conn.execute = AsyncMock()

        await db_service.guardar_estado(pool, 123, "ESPERANDO", {"key": "value"})
        conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_obtener_estado_exists(self):
        pool, conn = _mock_pool()
        conn.fetchrow = AsyncMock(return_value={"estado": "ESPERANDO", "datos_temporales": {"k": "v"}})

        result = await db_service.obtener_estado(pool, 123)
        assert result["estado"] == "ESPERANDO"

    @pytest.mark.asyncio
    async def test_obtener_estado_not_found(self):
        pool, conn = _mock_pool()
        conn.fetchrow = AsyncMock(return_value=None)

        result = await db_service.obtener_estado(pool, 123)
        assert result is None

    @pytest.mark.asyncio
    async def test_limpiar_estado(self):
        pool, conn = _mock_pool()
        conn.execute = AsyncMock()

        await db_service.limpiar_estado(pool, 123)
        conn.execute.assert_called_once()

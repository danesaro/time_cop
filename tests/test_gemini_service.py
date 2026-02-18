"""Tests for the Gemini AI service."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.schemas import ActividadGemini
from app.services.gemini_service import (
    GeminiProcessingError,
    _extract_json,
    procesar_actividades,
)


# ── _extract_json ────────────────────────────────────────────────────────────

class TestExtractJson:
    """Tests for JSON extraction from various Gemini response formats."""

    def test_plain_json(self):
        text = '{"actividades": [{"descripcion": "Test", "proyecto": "P1", "categoria": "proyectoFacturable", "horas_estimadas": 2}]}'
        result = _extract_json(text)
        data = json.loads(result)
        assert "actividades" in data

    def test_json_in_code_block(self):
        text = '```json\n{"actividades": [{"descripcion": "Test", "proyecto": "P1", "categoria": "proyectoFacturable", "horas_estimadas": 2}]}\n```'
        result = _extract_json(text)
        data = json.loads(result)
        assert "actividades" in data

    def test_json_in_plain_code_block(self):
        text = '```\n{"actividades": [{"descripcion": "Test", "proyecto": "P1", "categoria": "proyectoFacturable", "horas_estimadas": 2}]}\n```'
        result = _extract_json(text)
        data = json.loads(result)
        assert "actividades" in data

    def test_json_with_surrounding_text(self):
        text = 'Here is the result:\n{"actividades": [{"descripcion": "Test", "proyecto": "P1", "categoria": "proyectoFacturable", "horas_estimadas": 2}]}\nDone!'
        result = _extract_json(text)
        data = json.loads(result)
        assert "actividades" in data


# ── procesar_actividades ─────────────────────────────────────────────────────


class TestProcesarActividades:
    """Tests for the main Gemini processing function."""

    @pytest.mark.asyncio
    async def test_successful_processing(self):
        """Verify valid Gemini response is parsed into ActividadGemini objects."""
        response_json = json.dumps({
            "actividades": [
                {
                    "descripcion": "Reunión de planning del sprint",
                    "proyecto": "Proyecto Alpha",
                    "categoria": "proyectoFacturable",
                    "horas_estimadas": 2.0,
                },
                {
                    "descripcion": "Revisión de código",
                    "proyecto": "Proyecto Alpha",
                    "categoria": "proyectoFacturable",
                    "horas_estimadas": 3.0,
                },
            ]
        })

        mock_response = MagicMock()
        mock_response.text = response_json

        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock(return_value=mock_response)

        with patch("app.services.gemini_service._get_model", return_value=mock_model):
            result = await procesar_actividades("Hoy tuve reunión y revisé código")

        assert len(result) == 2
        assert isinstance(result[0], ActividadGemini)
        assert result[0].proyecto == "Proyecto Alpha"
        assert result[1].horas_estimadas == 3.0

    @pytest.mark.asyncio
    async def test_invalid_json_raises_error(self):
        """Verify GeminiProcessingError is raised for invalid JSON."""
        mock_response = MagicMock()
        mock_response.text = "This is not JSON at all"

        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock(return_value=mock_response)

        # Patch wait to make retries instant
        with patch("app.services.gemini_service._get_model", return_value=mock_model), \
             patch("app.services.gemini_service.wait_exponential", return_value=0):
            with pytest.raises(GeminiProcessingError, match="Invalid JSON"):
                await procesar_actividades("texto de prueba")

    @pytest.mark.asyncio
    async def test_empty_response_raises_error(self):
        """Verify GeminiProcessingError on empty response."""
        mock_response = MagicMock()
        mock_response.text = ""

        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock(return_value=mock_response)

        with patch("app.services.gemini_service._get_model", return_value=mock_model), \
             patch("app.services.gemini_service.wait_exponential", return_value=0):
            with pytest.raises(GeminiProcessingError, match="empty response"):
                await procesar_actividades("texto de prueba")

    @pytest.mark.asyncio
    async def test_invalid_category_raises_error(self):
        """Verify validation error for invalid category value."""
        response_json = json.dumps({
            "actividades": [
                {
                    "descripcion": "Test",
                    "proyecto": "Project",
                    "categoria": "categoriaInvalida",
                    "horas_estimadas": 2.0,
                }
            ]
        })

        mock_response = MagicMock()
        mock_response.text = response_json

        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock(return_value=mock_response)

        with patch("app.services.gemini_service._get_model", return_value=mock_model), \
             patch("app.services.gemini_service.wait_exponential", return_value=0):
            with pytest.raises(GeminiProcessingError, match="validation failed"):
                await procesar_actividades("texto de prueba")

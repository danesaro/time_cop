"""Tests for utility functions."""

from datetime import date

import pytest

from app.utils import (
    _emoji_categoria,
    fin_semana,
    formatear_registros,
    inicio_semana,
    parsear_fecha,
)


class TestParsearFecha:
    """Tests for date parsing from various formats."""

    def test_iso_format(self):
        assert parsear_fecha("2026-02-17") == date(2026, 2, 17)

    def test_slash_format(self):
        assert parsear_fecha("17/02/2026") == date(2026, 2, 17)

    def test_dash_format(self):
        assert parsear_fecha("17-02-2026") == date(2026, 2, 17)

    def test_with_whitespace(self):
        assert parsear_fecha("  2026-02-17  ") == date(2026, 2, 17)

    def test_invalid_date(self):
        assert parsear_fecha("not-a-date") is None

    def test_empty_string(self):
        assert parsear_fecha("") is None

    def test_partial_date(self):
        assert parsear_fecha("2026-02") is None


class TestInicioFinSemana:
    """Tests for week boundary calculations."""

    def test_inicio_semana_lunes(self):
        """Monday returns itself."""
        assert inicio_semana(date(2026, 2, 16)) == date(2026, 2, 16)  # Monday

    def test_inicio_semana_miercoles(self):
        """Wednesday returns the previous Monday."""
        assert inicio_semana(date(2026, 2, 18)) == date(2026, 2, 16)

    def test_inicio_semana_domingo(self):
        """Sunday returns Monday of the same week."""
        assert inicio_semana(date(2026, 2, 22)) == date(2026, 2, 16)

    def test_fin_semana_lunes(self):
        """Monday returns Sunday."""
        assert fin_semana(date(2026, 2, 16)) == date(2026, 2, 22)

    def test_fin_semana_domingo(self):
        """Sunday returns itself."""
        assert fin_semana(date(2026, 2, 22)) == date(2026, 2, 22)


class TestEmojiCategoria:
    """Tests for category emoji mapping."""

    def test_facturable(self):
        assert _emoji_categoria("proyectoFacturable") == "💰 "

    def test_no_facturable(self):
        assert _emoji_categoria("proyectoNoFacturable") == "📌 "

    def test_otros(self):
        assert _emoji_categoria("otrosNoFacturable") == "📎 "

    def test_unknown(self):
        assert _emoji_categoria("unknown") == ""


class TestFormatearRegistros:
    """Tests for record formatting."""

    def test_empty_records(self):
        result = formatear_registros([], date(2026, 2, 17))
        assert "No hay registros" in result

    def test_with_records(self):
        registros = [
            {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "proyecto": "Proyecto X",
                "descripcion": "Reunión de planning",
                "categoria": "proyectoFacturable",
                "horas_estimadas": "2.00",
            }
        ]
        result = formatear_registros(registros, date(2026, 2, 17))
        assert "Proyecto X" in result
        assert "Reunión de planning" in result
        assert "2.00" in result

"""Gemini AI service — processes natural-language activity descriptions into structured records."""

import json
import logging
import re
from typing import Optional

import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import get_settings
from app.models.schemas import ActividadGemini, RespuestaGemini

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """Eres un asistente que convierte descripciones informales de trabajo en registros profesionales.

Analiza el siguiente texto y extrae TODAS las actividades mencionadas. Para cada actividad:
- Descripción profesional y clara
- Proyecto asociado (infiere del contexto)
- Categoría: 'proyectoFacturable', 'proyectoNoFacturable', 'otrosNoFacturable'
- Horas estimadas (si no está explícito, estima razonablemente, un día debe tener OBLIGATORIAMENTE 8 horas de actividades)

RESPONDE ÚNICAMENTE con un JSON válido:
{
  "actividades": [
    {
      "descripcion": "...",
      "proyecto": "...",
      "categoria": "...",
      "horas_estimadas": 2.5
    }
  ]
}"""

_model: Optional[genai.GenerativeModel] = None


def _get_model() -> genai.GenerativeModel:
    """Lazy-initialise and return the Gemini model instance."""
    global _model
    if _model is None:
        genai.configure(api_key=get_settings().GEMINI_API_KEY)
        _model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config=genai.GenerationConfig(
                temperature=0.3,
                response_mime_type="application/json",
                max_output_tokens=4096,
            ),
        )
        logger.info("Gemini model initialised (gemini-2.5-flash, temp=0.3)")
    return _model


# ── Public API ───────────────────────────────────────────────────────────────

class GeminiProcessingError(Exception):
    """Raised when Gemini fails to return a valid response."""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((GeminiProcessingError, Exception)),
    reraise=True,
)
async def procesar_actividades(texto_usuario: str) -> list[ActividadGemini]:
    """Send user text to Gemini and return structured activities.

    Args:
        texto_usuario: The user's natural-language description of what they did.

    Returns:
        A list of validated ActividadGemini objects.

    Raises:
        GeminiProcessingError: If Gemini returns an invalid or empty response after retries.
    """
    model = _get_model()
    prompt = f"{_SYSTEM_PROMPT}\n\nTexto del usuario: {texto_usuario}"

    logger.info("Sending text to Gemini (%d chars)", len(texto_usuario))

    try:
        response = await model.generate_content_async(prompt)
    except Exception as exc:
        logger.error("Gemini API call failed: %s", exc)
        raise GeminiProcessingError(f"Error calling Gemini API: {exc}") from exc

    if not response.text:
        raise GeminiProcessingError("Gemini returned an empty response")

    raw_text = response.text.strip()
    logger.debug("Gemini raw response: %s", raw_text[:500])

    # Extract JSON from potential markdown code blocks
    json_str = _extract_json(raw_text)

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse Gemini JSON: %s | raw: %s", exc, raw_text[:300])
        raise GeminiProcessingError(f"Invalid JSON from Gemini: {exc}") from exc

    try:
        respuesta = RespuestaGemini(**data)
    except Exception as exc:
        logger.error("Pydantic validation failed: %s | data: %s", exc, data)
        raise GeminiProcessingError(f"Response validation failed: {exc}") from exc

    logger.info("Gemini returned %d activities", len(respuesta.actividades))
    return respuesta.actividades


def _extract_json(text: str) -> str:
    """Extract JSON from a string that may be wrapped in markdown code blocks.

    Args:
        text: Raw Gemini response text.

    Returns:
        The extracted JSON string.
    """
    # Try to find JSON in code blocks: ```json ... ``` or ``` ... ```
    pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Try to find a JSON object directly
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]

    return text

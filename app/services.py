import os
import json
import google.generativeai as genai

genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))

GEMINI_MODEL = "gemini-1.5-flash"

ANALYSIS_PROMPT = """Eres un asistente para gestión de quejas en hoteles.
Dado el siguiente texto transcrito de una interacción en recepción, extrae la información en JSON con exactamente estas claves:

{
  "categoria": "<una de: ruido | limpieza | facturación | temperatura | servicio_no_atendido | otro>",
  "problema": "<descripción concisa del problema reportado por el huésped>",
  "solucion_aplicada": "<qué hizo el recepcionista para resolver, o 'ninguna' si no se menciona>",
  "accion_sugerida": "<acción concreta recomendada para el supervisor>"
}

Responde ÚNICAMENTE con el JSON, sin texto adicional.

Transcripción:
{transcription}"""


def transcribe_audio(audio_path: str) -> tuple[str, float]:
    """
    Transcribes audio using Gemini. Returns (transcription_text, estimated_cost_usd).
    Falls back to Whisper if Gemini fails.
    """
    try:
        return _transcribe_with_gemini(audio_path)
    except Exception as gemini_err:
        print(f"[transcribe] Gemini failed ({gemini_err}), falling back to Whisper")
        return _transcribe_with_whisper(audio_path)


def _transcribe_with_gemini(audio_path: str) -> tuple[str, float]:
    model = genai.GenerativeModel(GEMINI_MODEL)

    with open(audio_path, "rb") as f:
        audio_bytes = f.read()

    ext = os.path.splitext(audio_path)[1].lower().lstrip(".")
    mime_map = {"mp3": "audio/mp3", "wav": "audio/wav", "ogg": "audio/ogg",
                "m4a": "audio/mp4", "webm": "audio/webm"}
    mime = mime_map.get(ext, "audio/wav")

    response = model.generate_content([
        "Transcribe el siguiente audio en español con la mayor fidelidad posible. "
        "Devuelve únicamente el texto transcrito.",
        {"mime_type": mime, "data": audio_bytes},
    ])

    text = response.text.strip()
    cost = _estimate_gemini_cost(response)
    return text, cost


def _transcribe_with_whisper(audio_path: str) -> tuple[str, float]:
    import whisper  # lazy import — only needed as fallback
    model = whisper.load_model("base")
    result = model.transcribe(audio_path, language="es")
    return result["text"].strip(), 0.0


def analyze_complaint(transcription: str) -> tuple[dict, float]:
    """
    Sends transcription to Gemini for structured analysis.
    Returns (result_dict, cost_usd).
    """
    model = genai.GenerativeModel(GEMINI_MODEL)
    prompt = ANALYSIS_PROMPT.format(transcription=transcription)
    response = model.generate_content(prompt)

    raw = response.text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    data = json.loads(raw.strip())
    cost = _estimate_gemini_cost(response)
    return data, cost


def _estimate_gemini_cost(response) -> float:
    """Rough cost estimate based on token counts for gemini-1.5-flash."""
    try:
        usage = response.usage_metadata
        input_tokens = usage.prompt_token_count or 0
        output_tokens = usage.candidates_token_count or 0
        # gemini-1.5-flash pricing (May 2025): ~$0.075/1M input, $0.30/1M output
        return (input_tokens * 0.075 + output_tokens * 0.30) / 1_000_000
    except Exception:
        return 0.0

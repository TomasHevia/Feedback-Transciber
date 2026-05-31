import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.oauth2 import service_account
from faster_whisper import WhisperModel
import torch

_whisper_model = None
load_dotenv()
credentials_path = os.getenv("ROUTE_CREDENTIALS")
project = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
location = os.getenv("GOOGLE_CLOUD_LOCATION")

if credentials_path:
    credentials = service_account.Credentials.from_service_account_file(
        credentials_path,
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )

    client = genai.Client(
        vertexai=True,
        project=project,
        location=location,
        credentials=credentials,
    )
else:
    client = genai.Client(
        vertexai=True,
        project=project,
        location=location,
    )

MODEL_NAME = os.getenv(
    "GOOGLE_CLOUD_MODEL",
    "gemini-2.5-flash"
)

ANALYSIS_PROMPT = """
Eres un asistente para gestión de quejas en hoteles.

Dado el siguiente texto transcrito de una interacción en recepción, extrae la información en JSON con exactamente estas claves:

{{
  "categoria": "<una de: ruido | limpieza | facturacion | temperatura | mantenimiento | internet_wifi | television | electricidad | agua | plomeria | check_in | check_out | reserva | sobreventa | habitacion_incorrecta | llaves_acceso | equipaje | estacionamiento | transporte | restaurante | desayuno | room_service | servicio_no_atendido | personal | seguridad | cobro_indebido | reembolso | amenidades | piscina | gimnasio | accesibilidad | otro>",
  "problema": "<descripción concisa del problema reportado por el huésped>",
  "solucion_aplicada": "<qué hizo el recepcionista para resolver o sugerir una solución, o 'ninguna' si no se menciona>",
  "accion_sugerida": "<acción concreta recomendada para el supervisor>"
}}

Responde ÚNICAMENTE con el JSON, sin texto adicional.

Transcripción:
{transcription}"""

TRANSCRIBE_PROMPT = """
Transcribe el siguiente audio en español con la mayor fidelidad posible.

Si detectas múltiples personas hablando:
- Identifica de forma aproximada cuántos participantes hay.
- Asigna etiquetas consecutivas: Persona 1, Persona 2, Persona 3, etc.
- Mantén la estructura conversacional.
- Cada intervención debe comenzar con la etiqueta correspondiente.
- Si no estás seguro de quién habla, utiliza la etiqueta más probable.
- No inventes contenido que no aparezca en el audio.

Formato esperado:

Participantes detectados: 2
Persona 1: Buenos días, tengo un problema con mi habitación.
Persona 2: Claro, ¿qué inconveniente presenta?
Persona 1: El aire acondicionado no funciona.

Devuelve únicamente la transcripción.
"""


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
    with open(audio_path, "rb") as f:
        audio_bytes = f.read()

    ext = os.path.splitext(audio_path)[1].lower().lstrip(".")
    mime_map = {"mp3": "audio/mpeg", "wav": "audio/wav", "ogg": "audio/ogg", "m4a": "audio/mp4", "webm": "audio/webm",}
    mime = mime_map.get(ext, "audio/wav")

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=[
            TRANSCRIBE_PROMPT,
            types.Part.from_bytes(
                data=audio_bytes,
                mime_type=mime,
            ),
        ],
    )

    text = response.text.strip()
    cost = _estimate_gemini_cost(response)

    return text, cost

def _get_whisper_model():
    global _whisper_model

    if _whisper_model is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

        _whisper_model = WhisperModel(
            "base",
            device=device,
            compute_type="float16" if device == "cuda" else "int8"
        )

    return _whisper_model


def _transcribe_with_whisper(audio_path: str) -> tuple[str, float]:
    model = _get_whisper_model()

    segments, info = model.transcribe(
        audio_path,
        language="es",
        beam_size=5
    )

    text = " ".join(segment.text.strip() for segment in segments)

    return text, 0.0


def analyze_complaint(transcription: str) -> tuple[dict, float]:
    """
    Sends transcription to Gemini for structured analysis.
    Returns (result_dict, cost_usd).
    """
    prompt = ANALYSIS_PROMPT.format(transcription=transcription)
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )

    raw = response.text.strip()
    # Strip markdown code fences if present
    if "```" in raw:
        import re
        raw = re.sub(r"```(?:json)?", "", raw).strip()
    # Extract JSON object in case Gemini adds surrounding text
    start, end = raw.find("{"), raw.rfind("}") + 1
    if start != -1 and end > start:
        raw = raw[start:end]
    data = json.loads(raw)
    cost = _estimate_gemini_cost(response)
    return data, cost


def _estimate_gemini_cost(response) -> float:
    """Rough cost estimate based on token counts for gemini-1.5-flash."""
    try:
        usage = response.usage_metadata
        input_tokens = getattr(usage, "prompt_token_count", 0) or 0
        output_tokens = getattr(usage, "candidates_token_count", 0) or 0
        # GEMINI FLASH 2.5 COST
        return (input_tokens * 0.075 + output_tokens * 0.30) / 1_000_000
    except Exception:
        return 0.0

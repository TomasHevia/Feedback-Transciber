import os
import json
from dotenv import load_dotenv
from google import genai
from google.oauth2 import service_account
from google.genai import types

try:
    from faster_whisper import WhisperModel
    import torch
    _WHISPER_AVAILABLE = True
except ImportError:
    _WHISPER_AVAILABLE = False

_whisper_model = None
load_dotenv()

project = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
location = os.getenv("GOOGLE_CLOUD_LOCATION")

credentials_path = os.getenv("ROUTE_CREDENTIALS")

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
    last_gemini_err = None
    for attempt in range(2):
        try:
            return _transcribe_with_gemini(audio_path)
        except Exception as e:
            last_gemini_err = e
            print(f"[transcribe] Gemini intento {attempt + 1}/2 falló: {e}")

    if not _WHISPER_AVAILABLE:
        raise RuntimeError(
            f"Gemini no pudo transcribir el audio ({last_gemini_err}). "
            "Whisper no está instalado. Por favor ingresa la transcripción manualmente."
        )

    print("[transcribe] Gemini falló dos veces, usando Whisper como respaldo")
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
    if not _WHISPER_AVAILABLE:
        raise RuntimeError("faster-whisper not installed")
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
    import re
    last_err = None
    for attempt in range(2):
        try:
            prompt = ANALYSIS_PROMPT.format(transcription=transcription)
            response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
            raw = response.text.strip()
            if "```" in raw:
                raw = re.sub(r"```(?:json)?", "", raw).strip()
            start, end = raw.find("{"), raw.rfind("}") + 1
            if start != -1 and end > start:
                raw = raw[start:end]
            data = json.loads(raw)
            cost = _estimate_gemini_cost(response)
            return data, cost
        except Exception as e:
            last_err = e
            print(f"[analyze] Intento {attempt + 1}/2 falló: {e}")
    raise last_err


REPORT_PROMPT = """
Eres un analista de calidad hotelera. Analiza las siguientes {total} quejas de recepción y genera un reporte ejecutivo en JSON con exactamente esta estructura (sin texto adicional):

{{
  "resumen": "<2-3 oraciones con el panorama general>",
  "periodo": "<descripción del rango de fechas cubierto>",
  "problemas_principales": [
    {{"categoria": "<slug>", "label": "<nombre legible>", "frecuencia": 0, "descripcion": "<patrón observado en las quejas>"}}
  ],
  "patrones_detectados": ["<patrón específico, ej: ruido concentrado en turno noche>"],
  "acciones_recomendadas": [
    {{"prioridad": "alta", "accion": "<acción concreta y específica>", "justificacion": "<por qué es prioritaria>"}}
  ],
  "quejas_criticas": [<id1>, <id2>],
  "conclusion": "<párrafo ejecutivo con cierre y próximos pasos>"
}}

Responde ÚNICAMENTE con el JSON, sin texto adicional.

Quejas a analizar:
{complaints_text}
"""


def generate_report(complaints: list) -> tuple[dict, float]:
    import re
    lines = []
    for c in complaints:
        lines.append(
            f"#{c.id} | {c.created_at.strftime('%d/%m/%Y')} | cat:{c.category}"
            + (f" | sesión:{c.session_label}" if c.session_label else "")
            + f" | problema:{c.problem or 'N/A'}"
            + f" | solución:{c.applied_solution or 'N/A'}"
            + f" | acción:{c.suggested_action or 'N/A'}"
        )
    complaints_text = "\n".join(lines)

    last_err = None
    for attempt in range(2):
        try:
            prompt = REPORT_PROMPT.format(total=len(complaints), complaints_text=complaints_text)
            response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
            raw = response.text.strip()
            if "```" in raw:
                raw = re.sub(r"```(?:json)?", "", raw).strip()
            start, end = raw.find("{"), raw.rfind("}") + 1
            if start != -1 and end > start:
                raw = raw[start:end]
            data = json.loads(raw)
            cost = _estimate_gemini_cost(response)
            return data, cost
        except Exception as e:
            last_err = e
            print(f"[report] Intento {attempt + 1}/2 falló: {e}")
    raise last_err


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

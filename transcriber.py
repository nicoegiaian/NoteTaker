"""
transcriber.py — Transcripción de audio con Whisper
Convierte el .mp4 de Teams en texto limpio.
"""

import whisper
import logging
from config import WHISPER_MODEL, IDIOMA_REUNIONES

log = logging.getLogger(__name__)

# El modelo se carga una sola vez en memoria (puede tardar la primera vez)
_modelo = None

def _cargar_modelo():
    global _modelo
    if _modelo is None:
        log.info(f"   Cargando modelo Whisper '{WHISPER_MODEL}' (primera vez puede demorar)...")
        _modelo = whisper.load_model(WHISPER_MODEL)
    return _modelo


def transcribir_audio(ruta_archivo: str) -> str:
    """
    Transcribe el archivo de audio/video y retorna el texto completo.
    
    Args:
        ruta_archivo: Ruta al archivo .mp4 de la grabación
        
    Returns:
        Texto completo de la reunión como string
    """
    modelo = _cargar_modelo()

    opciones = {
        "verbose": False,
        "task": "transcribe",
    }

    # Si se especificó idioma, usarlo para mayor velocidad y precisión
    if IDIOMA_REUNIONES:
        opciones["language"] = IDIOMA_REUNIONES

    resultado = modelo.transcribe(ruta_archivo, **opciones)

    # Construir texto completo desde los segmentos
    segmentos = resultado.get("segments", [])
    lineas = []

    for seg in segmentos:
        inicio  = _formatear_tiempo(seg["start"])
        texto   = seg["text"].strip()
        if texto:
            lineas.append(f"[{inicio}] {texto}")

    transcript = "\n".join(lineas)

    if not transcript.strip():
        raise ValueError("La transcripción está vacía. Verificá que el archivo de audio tenga contenido.")

    return transcript


def _formatear_tiempo(segundos: float) -> str:
    """Convierte segundos a formato mm:ss"""
    minutos = int(segundos // 60)
    segs    = int(segundos % 60)
    return f"{minutos:02d}:{segs:02d}"

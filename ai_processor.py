"""
ai_processor.py — Procesamiento con Claude API
Recibe la transcripción y devuelve las notas estructuradas.
"""

import os
import re
import anthropic
import logging
from config import PROYECTOS, PROYECTO_DESCONOCIDO

log = logging.getLogger(__name__)

# Cliente de Anthropic (se inicializa una vez)
_cliente = None

def _get_cliente():
    global _cliente
    if _cliente is None:
        _cliente = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _cliente


def detectar_proyecto(nombre_archivo: str) -> str:
    """
    Detecta a qué proyecto pertenece la reunión basándose en el nombre del archivo.
    
    Args:
        nombre_archivo: Nombre del archivo .mp4
        
    Returns:
        Nombre del proyecto detectado
    """
    nombre_lower = nombre_archivo.lower()
    for clave, proyecto in PROYECTOS.items():
        if clave.lower() in nombre_lower:
            log.info(f"   Proyecto detectado: {proyecto}")
            return proyecto

    log.warning(f"   No se detectó proyecto en '{nombre_archivo}' → asignando '{PROYECTO_DESCONOCIDO}'")
    return PROYECTO_DESCONOCIDO


def generar_notas(transcript: str, nombre_archivo: str) -> dict:
    """
    Envía la transcripción a Claude y recibe las notas estructuradas.
    
    Args:
        transcript:     Texto completo de la reunión
        nombre_archivo: Nombre del archivo para contexto
        
    Returns:
        Diccionario con todas las secciones de las notas
    """
    proyecto = detectar_proyecto(nombre_archivo)
    cliente  = _get_cliente()

    # Limitar tamaño del transcript para no exceder el contexto
    # Claude puede manejar hasta ~200k tokens pero limitamos para controlar costo
    MAX_CHARS = 80_000
    if len(transcript) > MAX_CHARS:
        log.warning(f"   Transcripción muy larga ({len(transcript)} chars), truncando a {MAX_CHARS}...")
        transcript = transcript[:MAX_CHARS] + "\n\n[... transcripción truncada por longitud ...]"

    prompt = f"""Sos un asistente experto en gestión de proyectos. Analizá la siguiente transcripción de una reunión de trabajo y generá notas estructuradas y accionables.

NOMBRE DE LA REUNIÓN: {nombre_archivo}
PROYECTO: {proyecto}

TRANSCRIPCIÓN:
{transcript}

---

Generá las notas en el siguiente formato JSON exacto (sin texto adicional antes o después):

{{
  "titulo": "Título descriptivo de la reunión (no solo el nombre del archivo)",
  "proyecto": "{proyecto}",
  "resumen": "Párrafo de 3-5 oraciones con el contexto, objetivo y principales conclusiones de la reunión. Escribilo en español, en tercera persona.",
  "acciones": [
    {{
      "descripcion": "Descripción clara y accionable de la tarea",
      "responsable": "Nombre de la persona responsable (o 'Por definir' si no se menciona)",
      "fecha_limite": "Fecha mencionada en formato DD/MM o 'Sin fecha definida'"
    }}
  ],
  "dependencias": [
    {{
      "descripcion": "Qué está bloqueado o condicionado",
      "depende_de": "De qué o quién depende"
    }}
  ],
  "proximos_pasos": [
    "Paso 1 concreto y verificable",
    "Paso 2 concreto y verificable"
  ],
  "participantes": ["Nombre 1", "Nombre 2"],
  "temas_pendientes": ["Tema que quedó sin resolver 1", "Tema 2"]
}}

Reglas importantes:
- Si no hay acciones, dependencias o temas pendientes, usá listas vacías []
- Todas las acciones deben ser específicas y accionables (no genéricas como "hacer seguimiento")
- Solo incluí información que esté en la transcripción, no inventes datos
- Respondé ÚNICAMENTE con el JSON, sin markdown, sin texto adicional
"""

    mensaje = cliente.messages.create(
        model="claude-opus-4-5",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    respuesta_texto = mensaje.content[0].text.strip()

    # Parsear el JSON de respuesta
    try:
        import json
        # A veces Claude envuelve el JSON en backticks, limpiamos eso
        respuesta_limpia = re.sub(r'^```(?:json)?\n?', '', respuesta_texto)
        respuesta_limpia = re.sub(r'\n?```$', '', respuesta_limpia)
        notas = json.loads(respuesta_limpia)
    except Exception as e:
        log.error(f"Error parseando respuesta JSON de Claude: {e}")
        log.error(f"Respuesta recibida: {respuesta_texto[:500]}")
        raise ValueError(f"Claude no devolvió un JSON válido: {e}")

    return notas

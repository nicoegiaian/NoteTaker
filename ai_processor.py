"""
ai_processor.py — Claude API (reemplaza Gemini)
Genera notas estructuradas de reuniones en formato JSON.
"""

import os
import re
import json
import logging
import requests
import urllib3
from config import PROYECTOS, PROYECTO_DESCONOCIDO

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
log = logging.getLogger(__name__)

CLAUDE_URL = "https://api.anthropic.com/v1/messages"


def detectar_proyecto(nombre_archivo: str) -> str:
    nombre_lower = nombre_archivo.lower()
    for clave, proyecto in PROYECTOS.items():
        if clave.lower() in nombre_lower:
            log.info(f"   Proyecto detectado: {proyecto}")
            return proyecto
    log.warning(f"   No se detecto proyecto en '{nombre_archivo}' -> '{PROYECTO_DESCONOCIDO}'")
    return PROYECTO_DESCONOCIDO


def generar_notas(transcript: str, nombre_archivo: str) -> dict:
    proyecto = detectar_proyecto(nombre_archivo)
    api_key  = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        raise ValueError("No se encontro ANTHROPIC_API_KEY en el archivo .env")

    MAX_CHARS = 180_000
    if len(transcript) > MAX_CHARS:
        log.warning(f"   Transcript muy largo, truncando a {MAX_CHARS} chars...")
        transcript = transcript[:MAX_CHARS] + "\n\n[... truncado ...]"

    prompt = f"""Sos un asistente experto en gestion de proyectos. Analiza el siguiente transcript de una reunion de Microsoft Teams.

Los nombres de los participantes son reales (vienen del sistema oficial de Teams).
Formato del transcript: "Nombre Apellido: texto que dijo"

REUNION: {nombre_archivo}
PROYECTO: {proyecto}

TRANSCRIPT:
{transcript}

---
Genera un JSON con exactamente estas claves:
- titulo: string con titulo descriptivo de la reunion
- proyecto: string con el nombre del proyecto ("{proyecto}")
- resumen: string con 3-5 oraciones sobre contexto, objetivo y conclusiones. En español, tercera persona.
- acciones: lista de objetos con claves "descripcion", "responsable", "fecha_limite"
- dependencias: lista de objetos con claves "descripcion", "depende_de"
- proximos_pasos: lista de strings
- participantes: lista de strings con nombres completos
- temas_pendientes: lista de strings

Reglas:
- Usa los nombres reales del transcript para responsables y participantes
- Si alguien dice "yo me encargo" identifica quien es por contexto
- Solo incluye informacion que este en el transcript, no inventes datos
- Si no hay acciones, dependencias o temas pendientes, usa listas vacias
- Responde SOLO con el JSON, sin texto adicional, sin bloques de codigo markdown"""

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 4096,
        "messages": [
            {"role": "user", "content": prompt}
        ],
    }

    respuesta = requests.post(
        CLAUDE_URL,
        headers=headers,
        json=payload,
        verify=False,
        timeout=120,
    )

    if respuesta.status_code != 200:
        raise ValueError(f"Error de Claude API: {respuesta.status_code} — {respuesta.text[:300]}")

    respuesta_json = respuesta.json()

    uso = respuesta_json.get("usage", {})
    log.info(f"   Tokens usados - entrada: {uso.get('input_tokens', '?')}, "
             f"salida: {uso.get('output_tokens', '?')}")

    try:
        texto = respuesta_json["content"][0]["text"].strip()
    except (KeyError, IndexError) as e:
        raise ValueError(f"Respuesta inesperada de Claude: {respuesta_json}") from e

    # Limpiar backticks por si acaso
    texto = re.sub(r'^```(?:json)?\n?', '', texto)
    texto = re.sub(r'\n?```$', '', texto)

    try:
        return json.loads(texto)
    except Exception:
        try:
            from json_repair import repair_json
            texto_reparado = repair_json(texto)
            resultado = json.loads(texto_reparado)
            log.warning("   JSON reparado automaticamente")
            return resultado
        except Exception as e:
            log.error(f"Error parseando JSON: {e}")
            log.error(f"Respuesta (primeros 500 chars): {texto[:500]}")
            raise ValueError(f"Claude no devolvio un JSON valido: {e}")
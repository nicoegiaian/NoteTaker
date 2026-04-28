"""
gemini_processor.py — Procesa minutas de Gemini en formato .docx
Extrae contenido y lo convierte al formato interno de notas.
"""

import json
import logging
import os
import re
import requests
import urllib3
from pathlib import Path
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
log = logging.getLogger(__name__)

CLAUDE_URL = "https://api.anthropic.com/v1/messages"


def es_minuta_gemini(nombre_archivo: str) -> bool:
    """Detecta si un .docx es una minuta generada por Gemini."""
    nombre_lower = nombre_archivo.lower()
    return (
        nombre_archivo.endswith(".docx") and
        "notes_by_gemini" in nombre_lower or
        "gemini" in nombre_lower
    )


def leer_docx(ruta: str) -> str:
    """Extrae texto plano del .docx."""
    from docx import Document
    doc = Document(ruta)
    texto = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
    return texto[:15000]


def convertir_a_notas(contenido: str, nombre_archivo: str) -> dict:
    """Usa Claude para convertir el contenido de Gemini al formato interno de notas."""
    from ai_processor import detectar_proyecto
    proyecto = detectar_proyecto(nombre_archivo)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    prompt = f"""Sos un asistente experto en gestión de proyectos. Te comparto una minuta de reunión generada por Gemini en formato .docx.

NOMBRE DEL ARCHIVO: {nombre_archivo}
PROYECTO: {proyecto}

CONTENIDO DE LA MINUTA:
{contenido}

Analizá el contenido y generá un JSON con exactamente estas claves:
- titulo: string con título descriptivo de la reunión
- proyecto: string con el nombre del proyecto ("{proyecto}")
- resumen: string con 3-5 oraciones sobre contexto, objetivo y conclusiones. En español, tercera persona.
- acciones: lista de objetos con claves "descripcion", "responsable", "fecha_limite". Extraé las acciones de la sección "Próximos pasos". El responsable está entre corchetes al inicio de cada ítem.
- dependencias: lista de objetos con claves "descripcion", "depende_de". Si no hay, lista vacía.
- proximos_pasos: lista de strings con los próximos pasos como texto simple.
- participantes: lista de strings con nombres completos de los participantes.
- temas_pendientes: lista de strings con temas sin resolución detectados.

Reglas:
- Extraé los responsables de los corchetes en "Próximos pasos": [Nombre] → responsable
- Si no hay fecha límite explícita, usá "Sin fecha definida"
- Solo incluí información que esté en el contenido, no inventes datos
- Respondé SOLO con el JSON, sin texto adicional ni bloques markdown"""

    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": prompt}],
    }

    resp = requests.post(CLAUDE_URL, headers=headers, json=payload, verify=False, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    log.info(f"   Tokens Gemini→notas - entrada: {data['usage']['input_tokens']}, salida: {data['usage']['output_tokens']}")

    texto = data["content"][0]["text"].strip()
    texto = re.sub(r'^```(?:json)?\n?', '', texto)
    texto = re.sub(r'\n?```$', '', texto)

    try:
        return json.loads(texto)
    except Exception:
        try:
            from json_repair import repair_json
            return json.loads(repair_json(texto))
        except Exception as e:
            raise ValueError(f"Claude no devolvió JSON válido: {e}")


def procesar_minuta_gemini(ruta_archivo: str) -> dict | None:
    """
    Pipeline completo: leer .docx → extraer contenido → convertir a notas.
    Retorna el dict de notas o None si falla.
    """
    nombre = Path(ruta_archivo).name
    log.info(f"[Gemini] Procesando minuta: {nombre}")

    try:
        contenido = leer_docx(ruta_archivo)
        if not contenido or len(contenido.strip()) < 100:
            log.warning(f"   Contenido muy corto, ignorando: {nombre}")
            return None

        notas = convertir_a_notas(contenido, nombre)
        log.info(f"   Notas extraídas para: {notas.get('proyecto', 'Sin proyecto')}")
        return notas

    except Exception as e:
        log.error(f"   Error procesando minuta Gemini: {e}")
        return None
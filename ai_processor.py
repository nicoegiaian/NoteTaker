"""
ai_processor.py — Claude API (reemplaza Gemini)
Genera notas estructuradas de reuniones en formato JSON.
"""

import os
import re
import json
import time
import logging
import requests
import urllib3
from pathlib import Path
from config import PROYECTOS, PROYECTO_DESCONOCIDO

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
log = logging.getLogger(__name__)

CLAUDE_URL = "https://api.anthropic.com/v1/messages"

# Códigos HTTP transitorios que ameritan reintento
_RETRY_CODES = {429, 529}


def detectar_proyecto(nombre_archivo: str) -> str:
    nombre_lower = nombre_archivo.lower()
    for clave, proyecto in PROYECTOS.items():
        if clave.lower() in nombre_lower:
            log.info(f"   Proyecto detectado: {proyecto}")
            return proyecto
    log.warning(f"   No se detecto proyecto en '{nombre_archivo}' -> '{PROYECTO_DESCONOCIDO}'")
    return PROYECTO_DESCONOCIDO


def _leer_prompt_notas() -> str:
    """Lee el prompt de clasificación y generación de notas desde el archivo externo."""
    from config import PROMPTS_FOLDER
    ruta = PROMPTS_FOLDER / "prompt_notas_reunion.txt"
    try:
        return ruta.read_text(encoding="utf-8")
    except Exception as e:
        raise ValueError(f"No se pudo leer el prompt de notas ({ruta}): {e}")


def _leer_glosario(proyecto: str) -> str:
    """Extrae la sección GLOSARIO / NOMBRES PROPIOS de la ficha del proyecto, para
    que la generación de notas normalice los nombres propios que la transcripción
    automática suele traer mal. Devuelve "" si no hay glosario."""
    from config import CONTEXTO_FOLDER
    ruta = Path(CONTEXTO_FOLDER) / f"contexto_{proyecto}.txt"
    if not ruta.exists():
        return ""
    try:
        texto = ruta.read_text(encoding="utf-8")
    except Exception:
        return ""
    header = "=== GLOSARIO / NOMBRES PROPIOS ==="
    i = texto.find(header)
    if i == -1:
        return ""
    resto = texto[i + len(header):]
    fin = resto.find("\n=== ")
    return (resto if fin == -1 else resto[:fin]).strip()


def _llamar_claude_con_retry(
    url: str,
    headers: dict,
    payload: dict,
    max_intentos: int = 4,
    backoff_base: float = 5.0,
) -> requests.Response:
    """
    POST a Claude API con reintentos exponenciales para errores transitorios.

    Esperas entre reintentos: 5s → 10s → 20s (backoff x2).
    Errores no transitorios (4xx/5xx reales) fallan de inmediato sin reintentar.

    Args:
        url: Endpoint de la API.
        headers: Headers HTTP del request.
        payload: Body JSON del request.
        max_intentos: Número máximo de intentos (default 4 = hasta 3 reintentos).
        backoff_base: Segundos base para el backoff exponencial (default 5s).

    Returns:
        requests.Response con status 200.

    Raises:
        ValueError: Si se agotan los intentos o el error no es reintentable.
    """
    for intento in range(1, max_intentos + 1):
        respuesta = requests.post(url, headers=headers, json=payload, verify=False, timeout=120)

        if respuesta.status_code == 200:
            return respuesta

        if respuesta.status_code in _RETRY_CODES and intento < max_intentos:
            espera = backoff_base * (2 ** (intento - 1))
            log.warning(
                f"   Claude API sobrecargada (HTTP {respuesta.status_code}), "
                f"reintento {intento}/{max_intentos - 1} en {espera:.0f}s..."
            )
            time.sleep(espera)
            continue

        # Error no reintentable o intentos agotados
        raise ValueError(f"Error de Claude API: {respuesta.status_code} — {respuesta.text[:300]}")

    raise ValueError("Se agotaron los reintentos a Claude API")


def generar_notas(transcript: str, nombre_archivo: str, tipo_forzado: str = None) -> dict:
    proyecto = detectar_proyecto(nombre_archivo)
    api_key  = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        raise ValueError("No se encontro ANTHROPIC_API_KEY en el archivo .env")

    MAX_CHARS = 180_000
    if len(transcript) > MAX_CHARS:
        log.warning(f"   Transcript muy largo, truncando a {MAX_CHARS} chars...")
        transcript = transcript[:MAX_CHARS] + "\n\n[... truncado ...]"

    prompt_template = _leer_prompt_notas()

    # Si el usuario forzó un tipo, se lo indicamos a Claude y saltamos la clasificación
    if tipo_forzado:
        tipo_override = f"TIPO DE REUNIÓN DEFINIDO POR EL USUARIO: {tipo_forzado}. No clasifiques, usá este tipo directamente."
        instruccion_tipo = f"El tipo ya fue definido: {tipo_forzado}. Pasá directamente al Paso 2."
        log.info(f"   Tipo de reunión forzado: {tipo_forzado}")
    else:
        tipo_override = ""
        instruccion_tipo = "Analizá el transcript y elegí el tipo que mejor represente el espíritu de la reunión."

    glosario = _leer_glosario(proyecto)
    prompt = prompt_template.replace("{{NOMBRE_ARCHIVO}}", nombre_archivo)
    prompt = prompt.replace("{{PROYECTO}}", proyecto)
    prompt = prompt.replace("{{TRANSCRIPT}}", transcript)
    prompt = prompt.replace("{{TIPO_OVERRIDE}}", tipo_override)
    prompt = prompt.replace("{{INSTRUCCION_TIPO}}", instruccion_tipo)
    prompt = prompt.replace("{{GLOSARIO}}", glosario or "Sin glosario definido para este proyecto.")

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

    respuesta = _llamar_claude_con_retry(CLAUDE_URL, headers=headers, payload=payload)

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

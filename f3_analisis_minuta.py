"""
f3_analisis_minuta.py — F3: Análisis cruzado de minutas
Cruza la minuta nueva con:
  1. Contexto del proyecto
  2. Minutas anteriores del mismo proyecto
  3. Tareas abiertas en Planner
"""

import os
import logging
import requests
import urllib3
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup

from config import PROYECTOS
from proyecto_watcher import (
    cargar_contexto, guardar_contexto, llamar_claude,
    registrar_tokens, escribir_novedad, CONTEXTO_FOLDER
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
log = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
MAX_MINUTAS_ANTERIORES = 5  # cuántas minutas previas incluir como contexto


def _detectar_proyecto_minuta(nombre_archivo: str) -> str | None:
    """Detecta el proyecto por el nombre del archivo de minuta."""
    nombre_lower = nombre_archivo.lower()
    for clave, proyecto in PROYECTOS.items():
        if clave.lower() in nombre_lower:
            return proyecto
    return None


def _leer_html_como_texto(ruta: str) -> str:
    """Extrae texto plano de un HTML de minuta."""
    try:
        contenido = Path(ruta).read_text(encoding="utf-8")
        soup = BeautifulSoup(contenido, "html.parser")
        return soup.get_text(separator="\n", strip=True)[:6000]
    except Exception as e:
        log.error(f"Error leyendo HTML: {e}")
        return ""


def _obtener_minutas_anteriores(output_folder: str, proyecto: str, excluir: str) -> list:
    """Obtiene las últimas N minutas del proyecto, excluyendo la actual."""
    carpeta = Path(output_folder)
    htmls = sorted(carpeta.glob("*.html"), key=lambda f: f.stat().st_mtime, reverse=True)

    minutas = []
    for html in htmls:
        if html.name == excluir:
            continue
        proyecto_detectado = _detectar_proyecto_minuta(html.name)
        if proyecto_detectado == proyecto:
            texto = _leer_html_como_texto(str(html))
            if texto:
                minutas.append({
                    "nombre": html.name,
                    "fecha": datetime.fromtimestamp(html.stat().st_mtime).strftime("%d/%m/%Y"),
                    "contenido": texto[:3000],
                })
        if len(minutas) >= MAX_MINUTAS_ANTERIORES:
            break

    return minutas


def _obtener_tareas_planner(proyecto: str) -> list:
    """Obtiene las tareas abiertas del plan del proyecto en Planner."""
    try:
        from auth_microsoft import obtener_token
        from config import PLANNER_PLANES

        plan_id = PLANNER_PLANES.get(proyecto)
        if not plan_id:
            log.warning(f"   Plan de Planner no encontrado para: {proyecto}")
            return []

        token = obtener_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        resp = requests.get(
            f"{GRAPH_BASE}/planner/plans/{plan_id}/tasks",
            headers=headers,
            verify=False,
            timeout=30,
        )

        if resp.status_code != 200:
            log.warning(f"   Error obteniendo tareas de Planner: {resp.status_code}")
            return []

        tareas = resp.json().get("value", [])
        return [
            {
                "titulo": t.get("title", ""),
                "completada": t.get("percentComplete", 0) == 100,
                "vencimiento": t.get("dueDateTime", "Sin fecha")[:10] if t.get("dueDateTime") else "Sin fecha",
            }
            for t in tareas
            if t.get("percentComplete", 0) < 100
        ]

    except Exception as e:
        log.warning(f"   Planner no disponible para F3: {e}")
        return []


def analizar_minuta_cruzada(notas: dict, nombre_archivo: str, ruta_html: str, output_folder: str) -> str | None:
    """
    Pipeline completo de F3.
    Retorna el análisis enriquecido como texto, o None si falla.
    """
    proyecto = notas.get("proyecto", "")
    if not proyecto or proyecto == "Sin Proyecto Asignado":
        log.info("[F3] Proyecto no identificado, saltando análisis cruzado")
        return None

    log.info(f"[F3] Iniciando análisis cruzado para: {proyecto}")

    # 1. Contexto del proyecto
    contexto = cargar_contexto(proyecto)

    # 2. Minutas anteriores
    minutas_anteriores = _obtener_minutas_anteriores(
        output_folder, proyecto, Path(ruta_html).name
    )
    log.info(f"[F3] Minutas anteriores encontradas: {len(minutas_anteriores)}")

    # 3. Tareas abiertas en Planner
    tareas_planner = _obtener_tareas_planner(proyecto)
    log.info(f"[F3] Tareas abiertas en Planner: {len(tareas_planner)}")

    # 4. Contenido de la minuta actual
    minuta_actual = _leer_html_como_texto(ruta_html)

    # 5. Armar contexto de minutas anteriores
    if minutas_anteriores:
        texto_minutas = "\n\n".join([
            f"--- MINUTA {m['fecha']}: {m['nombre']} ---\n{m['contenido']}"
            for m in minutas_anteriores
        ])
    else:
        texto_minutas = "Sin minutas anteriores disponibles."

    # 6. Armar lista de tareas de Planner
    if tareas_planner:
        texto_tareas = "\n".join([
            f"- {t['titulo']} (vence: {t['vencimiento']})"
            for t in tareas_planner
        ])
    else:
        texto_tareas = "Sin tareas abiertas en Planner."

    # Leer prompt desde archivo
    prompt_path = Path(CONTEXTO_FOLDER) / "Prompts" / "prompt_f3_analisis.txt"
    try:
        prompt_template = prompt_path.read_text(encoding="utf-8")
    except Exception as e:
        log.error(f"No se pudo leer prompt: {e}")
        return None

    prompt = prompt_template.replace("{{PROYECTO}}", proyecto)
    prompt = prompt.replace("{{CONTEXTO}}", contexto)
    prompt = prompt.replace("{{MINUTA}}", minuta_actual)
    prompt = prompt.replace("{{MINUTAS_ANTERIORES}}", texto_minutas)
    prompt = prompt.replace("{{TAREAS_PLANNER}}", texto_tareas)

    resultado = llamar_claude(prompt)
    texto_completo = resultado["texto"]

    # Separar análisis del contexto actualizado
    partes = texto_completo.split("📌 CONTEXTO ACTUALIZADO DEL PROYECTO:")
    analisis = partes[0].strip()

    if len(partes) > 1:
        nuevo_contexto = partes[1].strip()
        if nuevo_contexto != "SIN_CAMBIOS":
            guardar_contexto(proyecto, nuevo_contexto)
            log.info(f"[F3] Contexto actualizado para {proyecto}")

    # Publicar en Teams via carpeta de novedades
    escribir_novedad(proyecto, analisis, "f3_minuta")
    registrar_tokens(proyecto, "F3_Minuta", resultado["input_tokens"], resultado["output_tokens"])

    log.info(f"[F3] Análisis cruzado completado para {proyecto}")
    return analisis
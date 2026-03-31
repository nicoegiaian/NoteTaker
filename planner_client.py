"""
planner_client.py — Crea tareas en Microsoft Planner
Usa el token de auth_microsoft.py para llamar a la Graph API.
Sin Playwright, sin servidor local.
"""

import json
import logging
import os
import re
import requests
import urllib3
from datetime import datetime
from config import PLANNER_PLANES

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
log = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def _headers() -> dict:
    from auth_microsoft import obtener_token
    token = obtener_token()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    }


def _buscar_plan_id(nombre_plan: str) -> str:
    """Busca el ID del plan en Planner por nombre exacto."""

    # Primero buscar en cache
    if nombre_plan in PLANNER_PLANES and PLANNER_PLANES[nombre_plan]:
        log.info(f"   Plan '{nombre_plan}' en cache")
        return PLANNER_PLANES[nombre_plan]

    log.info(f"   Buscando plan '{nombre_plan}' en Planner...")

    resp = requests.get(
        f"{GRAPH_BASE}/me/planner/plans",
        headers=_headers(),
        verify=False,
        timeout=30,
    )

    if resp.status_code != 200:
        raise ValueError(f"Error buscando planes: {resp.status_code} — {resp.text[:200]}")

    planes = resp.json().get("value", [])
    log.info(f"   Planes disponibles: {[p['title'] for p in planes]}")

    for plan in planes:
        if plan["title"].lower().strip() == nombre_plan.lower().strip():
            plan_id = plan["id"]
            log.info(f"   Plan encontrado: '{nombre_plan}'")
            PLANNER_PLANES[nombre_plan] = plan_id
            _guardar_cache_planes()
            return plan_id

    raise ValueError(
        f"No se encontro el plan '{nombre_plan}'. "
        f"Disponibles: {[p['title'] for p in planes]}"
    )


def _guardar_cache_planes():
    """Persiste el cache de IDs en config.py."""
    try:
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.py")
        with open(config_path, "r", encoding="utf-8") as f:
            contenido = f.read()

        nuevo_dict = json.dumps(PLANNER_PLANES, ensure_ascii=False, indent=4)
        contenido_nuevo = re.sub(
            r'PLANNER_PLANES\s*=\s*\{[^}]*\}',
            f'PLANNER_PLANES = {nuevo_dict}',
            contenido,
            flags=re.DOTALL,
        )

        with open(config_path, "w", encoding="utf-8") as f:
            f.write(contenido_nuevo)
    except Exception as e:
        log.warning(f"   No se pudo guardar cache: {e}")


def _obtener_bucket_id(plan_id: str) -> str:
    """Obtiene el bucket 'Pendiente' o el primero que no sea 'Completado'."""
    resp = requests.get(
        f"{GRAPH_BASE}/planner/plans/{plan_id}/buckets",
        headers=_headers(),
        verify=False,
        timeout=30,
    )

    if resp.status_code != 200:
        raise ValueError(f"Error obteniendo buckets: {resp.status_code}")

    buckets = resp.json().get("value", [])
    if not buckets:
        raise ValueError("El plan no tiene buckets")

    log.info(f"   Buckets disponibles: {[b['name'] for b in buckets]}")

    # Buscar "Pendiente" primero (o variantes comunes)
    nombres_pendiente = ["pendiente", "pending", "to do", "por hacer", "backlog", "nueva", "nuevo"]
    for b in buckets:
        if b["name"].lower().strip() in nombres_pendiente:
            log.info(f"   Bucket seleccionado: '{b['name']}'")
            return b["id"]

    # Si no hay bucket "Pendiente", usar cualquiera que no sea "Completado"
    nombres_completado = ["completado", "completed", "done", "terminado", "cerrado", "closed"]
    for b in buckets:
        if b["name"].lower().strip() not in nombres_completado:
            log.info(f"   Bucket seleccionado: '{b['name']}'")
            return b["id"]

    # Último recurso: usar el primero
    log.warning(f"   Usando primer bucket por defecto: '{buckets[0]['name']}'")
    return buckets[0]["id"]


def _crear_tarea(plan_id: str, bucket_id: str, accion: dict) -> bool:
    """Crea una tarea individual en Planner."""
    titulo = accion.get("descripcion", "Tarea sin titulo")[:255]

    payload = {
        "planId":   plan_id,
        "bucketId": bucket_id,
        "title":    titulo,
    }

    # Fecha limite
    fecha_str = accion.get("fecha_limite", "")
    if fecha_str and fecha_str != "Sin fecha definida":
        try:
            partes = fecha_str.split("/")
            if len(partes) == 2:
                dia, mes = int(partes[0]), int(partes[1])
                anio = datetime.now().year
                fecha_dt = datetime(anio, mes, dia)
                if fecha_dt < datetime.now():
                    fecha_dt = datetime(anio + 1, mes, dia)
                payload["dueDateTime"] = fecha_dt.strftime("%Y-%m-%dT00:00:00Z")
        except Exception:
            pass

    resp = requests.post(
        f"{GRAPH_BASE}/planner/tasks",
        headers=_headers(),
        json=payload,
        verify=False,
        timeout=30,
    )

    if resp.status_code in (200, 201):
        return True
    else:
        log.error(f"   Error creando '{titulo[:40]}': {resp.status_code} — {resp.text[:150]}")
        return False


def crear_tareas_en_planner(acciones: list, proyecto: str) -> str:
    """
    Crea todas las acciones como tareas en el plan correspondiente.
    Retorna mensaje de resultado.
    """
    if not acciones:
        return "No hay acciones para crear"

    log.info(f"[Planner] Creando {len(acciones)} tareas en '{proyecto}'...")

    try:
        plan_id   = _buscar_plan_id(proyecto)
        bucket_id = _obtener_bucket_id(plan_id)
    except Exception as e:
        log.error(f"[Planner] Error preparando plan: {e}")
        return f"Error: {e}"

    creadas = 0
    errores = 0

    for accion in acciones:
        if _crear_tarea(plan_id, bucket_id, accion):
            creadas += 1
            log.info(f"   Tarea creada: {accion.get('descripcion', '')[:50]}")
        else:
            errores += 1

    if errores == 0:
        resultado = f"{creadas} tareas creadas en '{proyecto}'"
    else:
        resultado = f"{creadas} creadas, {errores} con error en '{proyecto}'"

    log.info(f"[Planner] {resultado}")
    return resultado

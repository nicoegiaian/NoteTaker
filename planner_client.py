"""
planner_client.py — Crea y organiza tareas en Microsoft Planner
- Titulos con contexto: [DD/MM · Nombre reunion] Descripcion
- Descripcion detallada en cada tarea
- Buckets temporales creados automaticamente
- Tareas movidas entre buckets al procesar cada minuta
"""

import json
import logging
import os
import re
import requests
import urllib3
from datetime import datetime, timedelta
from config import PLANNER_PLANES

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
log = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# Buckets temporales — orden de mas reciente a mas antiguo
BUCKETS_TEMPORALES = [
    "Esta semana",
    "Hace 2 semanas",
    "Hace 3 semanas",
    "Hace +1 mes",
]

# Cuantos dias corresponde cada bucket
BUCKET_DIAS = {
    "Esta semana":    7,
    "Hace 2 semanas": 14,
    "Hace 3 semanas": 21,
    "Hace +1 mes":    999,
}


def _headers() -> dict:
    from auth_microsoft import obtener_token
    token = obtener_token()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    }


def _buscar_plan_id(nombre_plan: str) -> str:
    """Busca el ID del plan en Planner por nombre exacto."""
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


def _obtener_todos_buckets(plan_id: str) -> list:
    """Retorna todos los buckets del plan."""
    resp = requests.get(
        f"{GRAPH_BASE}/planner/plans/{plan_id}/buckets",
        headers=_headers(),
        verify=False,
        timeout=30,
    )
    if resp.status_code != 200:
        raise ValueError(f"Error obteniendo buckets: {resp.status_code}")
    return resp.json().get("value", [])


def _crear_bucket(plan_id: str, nombre: str, orden: int) -> str:
    """Crea un bucket nuevo en el plan y retorna su ID."""
    resp = requests.post(
        f"{GRAPH_BASE}/planner/buckets",
        headers=_headers(),
        json={
            "name":   nombre,
            "planId": plan_id,
        },
        verify=False,
        timeout=30,
    )
    if resp.status_code in (200, 201):
        bucket_id = resp.json()["id"]
        log.info(f"   Bucket creado: '{nombre}'")
        return bucket_id
    else:
        raise ValueError(f"Error creando bucket '{nombre}': {resp.status_code} — {resp.text[:200]}")


def _asegurar_buckets_temporales(plan_id: str) -> dict:
    """
    Verifica que existan los 4 buckets temporales.
    Los crea automaticamente si no existen.
    Retorna dict {nombre_bucket: id_bucket}.
    """
    buckets_existentes = _obtener_todos_buckets(plan_id)
    mapa = {b["name"]: b["id"] for b in buckets_existentes}

    for i, nombre in enumerate(BUCKETS_TEMPORALES):
        if nombre not in mapa:
            log.info(f"   Bucket '{nombre}' no existe, creando...")
            bucket_id = _crear_bucket(plan_id, nombre, i)
            mapa[nombre] = bucket_id

    return mapa


def _bucket_segun_fecha(fecha_creacion: datetime) -> str:
    """Retorna el nombre del bucket correcto segun la antiguedad."""
    dias = (datetime.now() - fecha_creacion).days
    if dias <= 7:
        return "Esta semana"
    elif dias <= 14:
        return "Hace 2 semanas"
    elif dias <= 21:
        return "Hace 3 semanas"
    else:
        return "Hace +1 mes"


def _mover_tareas_vencidas(plan_id: str, mapa_buckets: dict):
    """
    Revisa las tareas pendientes y las mueve al bucket correcto
    segun cuantos dias pasaron desde que fueron creadas.
    Se ejecuta cada vez que se procesa una nueva minuta.
    """
    log.info("   Reorganizando tareas por antiguedad...")

    # Obtener todas las tareas del plan
    resp = requests.get(
        f"{GRAPH_BASE}/planner/plans/{plan_id}/tasks",
        headers=_headers(),
        verify=False,
        timeout=30,
    )

    if resp.status_code != 200:
        log.warning(f"   No se pudieron obtener tareas para reorganizar: {resp.status_code}")
        return

    tareas = resp.json().get("value", [])
    ids_buckets_temporales = set(mapa_buckets.values())
    movidas = 0

    for tarea in tareas:
        # Solo mover tareas no completadas que esten en buckets temporales
        if tarea.get("percentComplete", 0) == 100:
            continue
        if tarea.get("bucketId") not in ids_buckets_temporales:
            continue

        # Calcular bucket correcto segun fecha de creacion
        fecha_str = tarea.get("createdDateTime", "")
        if not fecha_str:
            continue

        try:
            fecha_creacion = datetime.fromisoformat(fecha_str.replace("Z", "+00:00")).replace(tzinfo=None)
            bucket_correcto = _bucket_segun_fecha(fecha_creacion)
            bucket_id_correcto = mapa_buckets[bucket_correcto]

            if tarea["bucketId"] != bucket_id_correcto:
                # Mover la tarea — requiere etag para el PATCH
                resp_detalle = requests.get(
                    f"{GRAPH_BASE}/planner/tasks/{tarea['id']}",
                    headers=_headers(),
                    verify=False,
                    timeout=15,
                )
                if resp_detalle.status_code != 200:
                    continue

                etag = resp_detalle.headers.get("ETag", "")
                headers_patch = _headers()
                headers_patch["If-Match"] = etag
                headers_patch["Prefer"] = "return=representation"

                requests.patch(
                    f"{GRAPH_BASE}/planner/tasks/{tarea['id']}",
                    headers=headers_patch,
                    json={"bucketId": bucket_id_correcto},
                    verify=False,
                    timeout=15,
                )
                movidas += 1
        except Exception as e:
            log.warning(f"   Error moviendo tarea: {e}")
            continue

    if movidas > 0:
        log.info(f"   {movidas} tareas reorganizadas por antiguedad")
    else:
        log.info("   Tareas ya en el bucket correcto")


def _titulo_con_contexto(descripcion: str, titulo_reunion: str, fecha: str) -> str:
    """
    Genera el titulo de la tarea con contexto de reunion y fecha.
    Formato: [DD/MM · Nombre reunion] Descripcion
    Truncado a 255 chars (limite de Planner).
    """
    # Limpiar el titulo de la reunion para que sea conciso
    titulo_corto = titulo_reunion[:40].strip()
    if len(titulo_reunion) > 40:
        titulo_corto += "..."

    prefijo  = f"[{fecha} · {titulo_corto}] "
    titulo   = prefijo + descripcion
    return titulo[:255]


def _descripcion_tarea(accion: dict, titulo_reunion: str, proyecto: str, fecha: str) -> str:
    """Genera la descripcion detallada de la tarea."""
    lineas = [
        f"Reunion: {titulo_reunion}",
        f"Proyecto: {proyecto}",
        f"Fecha: {fecha}",
        f"Responsable: {accion.get('responsable', 'Por definir')}",
        "",
        "Generado automaticamente por NoteTaker Bot",
    ]
    return "\n".join(lineas)


def _crear_tarea(plan_id: str, bucket_id: str, accion: dict,
                 titulo_reunion: str, proyecto: str, fecha: str) -> bool:
    """Crea una tarea con titulo contextual y descripcion detallada."""

    titulo = _titulo_con_contexto(
        accion.get("descripcion", "Tarea sin titulo"),
        titulo_reunion,
        fecha,
    )

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

    if resp.status_code not in (200, 201):
        log.error(f"   Error creando '{titulo[:50]}': {resp.status_code} — {resp.text[:150]}")
        return False

    # Agregar descripcion detallada a los detalles de la tarea
    tarea_id = resp.json().get("id")
    if tarea_id:
        try:
            # Los detalles requieren etag
            resp_det = requests.get(
                f"{GRAPH_BASE}/planner/tasks/{tarea_id}/details",
                headers=_headers(),
                verify=False,
                timeout=15,
            )
            if resp_det.status_code == 200:
                etag = resp_det.headers.get("ETag", "")
                headers_patch = _headers()
                headers_patch["If-Match"] = etag

                descripcion = _descripcion_tarea(accion, titulo_reunion, proyecto, fecha)
                requests.patch(
                    f"{GRAPH_BASE}/planner/tasks/{tarea_id}/details",
                    headers=headers_patch,
                    json={"description": descripcion},
                    verify=False,
                    timeout=15,
                )
        except Exception as e:
            log.warning(f"   No se pudo agregar descripcion: {e}")

    return True


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


def crear_tareas_en_planner(acciones: list, proyecto: str,
                             titulo_reunion: str = "") -> str:
    """
    Punto de entrada principal.
    1. Asegura que existan los buckets temporales
    2. Mueve tareas viejas al bucket correcto
    3. Crea las nuevas tareas en 'Esta semana'
    """
    if not acciones:
        return "No hay acciones para crear"

    # Filtro selectivo (SEL): crear solo las acciones marcadas por el LLM.
    # Si el campo falta (nota vieja), se crea igual por retrocompatibilidad.
    total = len(acciones)
    acciones = [a for a in acciones if a.get("crear_en_planner", True)]
    omitidas = total - len(acciones)
    if omitidas:
        log.info(f"[Planner] {omitidas} de {total} acciones omitidas por baja confianza")
    if not acciones:
        return f"Sin tareas para crear ({omitidas} omitidas por baja confianza)"

    fecha_hoy = datetime.now().strftime("%d/%m")
    log.info(f"[Planner] Creando {len(acciones)} tareas en '{proyecto}'...")

    try:
        plan_id      = _buscar_plan_id(proyecto)
        mapa_buckets = _asegurar_buckets_temporales(plan_id)
        bucket_hoy   = mapa_buckets["Esta semana"]
    except Exception as e:
        log.error(f"[Planner] Error preparando plan: {e}")
        return f"Error: {e}"

    # Mover tareas existentes al bucket correcto segun antiguedad
    _mover_tareas_vencidas(plan_id, mapa_buckets)

    # Crear las nuevas tareas en "Esta semana"
    creadas = 0
    errores = 0

    for accion in acciones:
        if _crear_tarea(plan_id, bucket_hoy, accion, titulo_reunion, proyecto, fecha_hoy):
            creadas += 1
            log.info(f"   Tarea creada: {accion.get('descripcion', '')[:50]}")
        else:
            errores += 1

    if errores == 0:
        resultado = f"{creadas} tareas creadas en '{proyecto}'"
    else:
        resultado = f"{creadas} creadas, {errores} con error en '{proyecto}'"
    if omitidas:
        resultado += f" ({omitidas} omitidas por baja confianza)"

    log.info(f"[Planner] {resultado}")
    return resultado

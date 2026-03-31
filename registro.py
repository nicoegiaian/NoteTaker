"""
registro.py — Registro de archivos procesados
Usa el UUID de sesion de Teams como clave de duplicado.
El UUID es el identificador unico que Teams asigna a cada grabacion.
UUID diferente = reunion diferente, siempre.
"""

import os
import re
import json
import logging
from pathlib import Path
from datetime import datetime

log = logging.getLogger(__name__)

REGISTRO_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "registro_procesados.json"
)


def _extraer_uuid_vtt(nombre_o_ruta: str) -> str:
    """
    Extrae el UUID de sesion del archivo .vtt.
    Si solo se pasa el nombre (sin ruta), busca el archivo en Recordings.
    Retorna None si no puede leer el archivo.
    """
    ruta = Path(nombre_o_ruta)

    # Si no existe como ruta absoluta, buscar en la carpeta de Recordings
    if not ruta.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv()
            recordings = os.getenv("ONEDRIVE_RECORDINGS_PATH", "")
            ruta = Path(recordings) / ruta.name
        except Exception:
            pass

    if not ruta.exists():
        return None

    try:
        with open(ruta, "r", encoding="utf-8") as f:
            contenido = f.read()
        uuids = re.findall(
            r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})/',
            contenido
        )
        return uuids[0] if uuids else None
    except Exception:
        return None


def _clave_desde_uuid(uuid: str) -> str:
    return f"uuid:{uuid}"


def _clave_fallback(nombre_archivo: str) -> str:
    """
    Fallback si no se puede leer el UUID.
    Usa nombre normalizado sin timestamps.
    """
    stem = Path(nombre_archivo).stem
    stem = re.sub(r'_\d{6}$', '', stem).strip()   # elimina _HHMMSS
    stem = re.sub(r'-\d{8}_\d{6}UTC', '', stem)   # elimina fecha Teams
    return f"nombre:{stem.lower()}"


def _cargar() -> dict:
    if not os.path.exists(REGISTRO_FILE):
        return {}
    try:
        with open(REGISTRO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _guardar(registro: dict):
    with open(REGISTRO_FILE, "w", encoding="utf-8") as f:
        json.dump(registro, f, ensure_ascii=False, indent=2)


def ya_procesado(nombre_archivo: str) -> bool:
    """
    Retorna True si esta sesion ya fue procesada.
    Usa UUID como clave primaria, nombre como fallback.
    """
    registro = _cargar()

    # Intentar por UUID primero
    uuid = _extraer_uuid_vtt(nombre_archivo)
    if uuid:
        clave = _clave_desde_uuid(uuid)
        if clave in registro:
            log.info(f"   Duplicado detectado por UUID: {uuid}")
            return True
        return False

    # Fallback por nombre
    clave = _clave_fallback(nombre_archivo)
    if clave in registro:
        log.info(f"   Duplicado detectado por nombre: {clave}")
        return True
    return False


def marcar_procesado(nombre_archivo: str, ruta_output: str):
    """Registra una sesion como procesada."""
    registro = _cargar()

    uuid = _extraer_uuid_vtt(nombre_archivo)
    if uuid:
        clave = _clave_desde_uuid(uuid)
    else:
        clave = _clave_fallback(nombre_archivo)

    registro[clave] = {
        "nombre_original": Path(nombre_archivo).name,
        "uuid":            uuid or "desconocido",
        "procesado_el":    datetime.now().strftime("%d/%m/%Y %H:%M"),
        "output":          ruta_output,
    }
    _guardar(registro)
    log.info(f"   Registrado: {clave}")


def obtener_info(nombre_archivo: str) -> dict:
    """Retorna info de procesamiento si existe."""
    registro = _cargar()

    uuid = _extraer_uuid_vtt(nombre_archivo)
    if uuid:
        clave = _clave_desde_uuid(uuid)
    else:
        clave = _clave_fallback(nombre_archivo)

    return registro.get(clave, {})

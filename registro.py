"""
registro.py — Registro de archivos procesados
Detecta duplicados y lleva control de .vtt procesados.
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime

log = logging.getLogger(__name__)

REGISTRO_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "registro_procesados.json"
)


def _cargar() -> dict:
    """Carga el registro desde disco."""
    if not os.path.exists(REGISTRO_FILE):
        return {}
    try:
        with open(REGISTRO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _guardar(registro: dict):
    """Guarda el registro en disco."""
    with open(REGISTRO_FILE, "w", encoding="utf-8") as f:
        json.dump(registro, f, ensure_ascii=False, indent=2)


def ya_procesado(nombre_archivo: str) -> bool:
    """Retorna True si el archivo ya fue procesado anteriormente."""
    registro = _cargar()
    # Comparar solo el nombre base sin ruta
    nombre_base = Path(nombre_archivo).name
    return nombre_base in registro


def marcar_procesado(nombre_archivo: str, ruta_output: str):
    """Registra un archivo como procesado exitosamente."""
    registro = _cargar()
    nombre_base = Path(nombre_archivo).name
    registro[nombre_base] = {
        "procesado_el": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "output": ruta_output,
    }
    _guardar(registro)
    log.info(f"   Registrado como procesado: {nombre_base}")


def obtener_info(nombre_archivo: str) -> dict:
    """Retorna la info de procesamiento de un archivo si existe."""
    registro = _cargar()
    nombre_base = Path(nombre_archivo).name
    return registro.get(nombre_base, {})

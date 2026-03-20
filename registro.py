"""
registro.py — Registro de archivos procesados
Detecta duplicados usando nombre base + fecha de la reunion.
Permite reuniones recurrentes con el mismo titulo en distintas fechas.

Formato de nombre Teams:
  "Reunion Semanal-20260317_150432UTC-Meeting Recording.vtt"
   -> clave: "reunion semanal - 20260317"
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


def _extraer_clave(nombre_archivo: str) -> str:
    """
    Extrae una clave unica combinando nombre de reunion + fecha.

    Casos que maneja:
      "Reunion Semanal-20260317_150432UTC-Meeting Recording.vtt"
        -> "reunion semanal - 20260317"

      "MVP Ola 0 - Revision escenarios-20260315_120000UTC-Meeting Recording.vtt"
        -> "mvp ola 0 - revision escenarios - 20260315"

      "Reunion sin fecha_105123.vtt"  (timestamp de descarga, sin fecha Teams)
        -> "reunion sin fecha"        (solo nombre, sin fecha)
    """
    stem = Path(nombre_archivo).stem

    # Intentar extraer fecha en formato Teams: YYYYMMDD
    match_fecha = re.search(r'(\d{8})_\d{6}UTC', stem)
    if match_fecha:
        fecha = match_fecha.group(1)  # ej: "20260317"
        # Tomar todo lo que viene antes de la fecha como nombre
        nombre_parte = stem[:match_fecha.start()].strip(" -_")
        clave = f"{nombre_parte} - {fecha}".lower().strip()
    else:
        # Sin fecha Teams — eliminar solo el timestamp de descarga (_HHMMSS)
        nombre_limpio = re.sub(r'_\d{6}$', '', stem).strip()
        clave = nombre_limpio.lower().strip()

    return clave


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
    Retorna True si esta reunion (mismo titulo Y misma fecha) ya fue procesada.
    Reuniones recurrentes con distinta fecha NO se consideran duplicadas.
    """
    registro = _cargar()
    clave = _extraer_clave(nombre_archivo)
    resultado = clave in registro
    if resultado:
        log.info(f"   Clave duplicada encontrada: '{clave}'")
    return resultado


def marcar_procesado(nombre_archivo: str, ruta_output: str):
    """Registra una reunion como procesada exitosamente."""
    registro = _cargar()
    clave = _extraer_clave(nombre_archivo)
    registro[clave] = {
        "nombre_original": Path(nombre_archivo).name,
        "procesado_el":    datetime.now().strftime("%d/%m/%Y %H:%M"),
        "output":          ruta_output,
    }
    _guardar(registro)
    log.info(f"   Registrado: '{clave}'")


def obtener_info(nombre_archivo: str) -> dict:
    """Retorna la info de procesamiento si existe."""
    registro = _cargar()
    clave = _extraer_clave(nombre_archivo)
    return registro.get(clave, {})

# ============================================================
#  CONFIG.PY — Loader de configuración.
#
#  Ya NO se edita a mano (salvo PLANNER_PLANES, ver abajo): toda la
#  configuración vive en `configuracion.toml`. Este archivo solo la lee
#  con tomllib y la expone con los nombres que usa el resto del código.
# ============================================================

import tomllib
from pathlib import Path

_RUTA_TOML = Path(__file__).with_name("configuracion.toml")
try:
    with open(_RUTA_TOML, "rb") as _f:
        _cfg = tomllib.load(_f)
except FileNotFoundError as e:
    raise FileNotFoundError(
        f"No se encontró el archivo de configuración: {_RUTA_TOML}"
    ) from e

# ── General ──────────────────────────────────────────────
WHISPER_MODEL             = _cfg["general"]["whisper_model"]
IDIOMA_REUNIONES          = _cfg["general"]["idioma_reuniones"]
ESPERA_SINCRONIZACION_SEG = _cfg["general"]["espera_sincronizacion_seg"]
PROYECTO_DESCONOCIDO      = _cfg["general"]["proyecto_desconocido"]

# ── Mapeos de proyecto ───────────────────────────────────
# Palabra clave → proyecto (para catalogar asuntos/nombres). Orden preservado.
PROYECTOS             = _cfg["proyectos_por_palabra_clave"]
# Carpeta → proyecto (monitoreo de archivos F1b en proyecto_watcher).
PROYECTOS_POR_CARPETA = _cfg["proyectos_por_carpeta"]

# ── Archivos y rutas ─────────────────────────────────────
EXTENSIONES_SOPORTADAS = set(_cfg["archivos"]["extensiones_soportadas"])
CONTEXTO_FOLDER  = _cfg["rutas"]["contexto_folder"]
NOVEDADES_FOLDER = _cfg["rutas"]["novedades_folder"]
MAILS_FOLDER     = _cfg["rutas"]["mails_folder"]
COLA_FILE        = _cfg["rutas"]["cola_file"]
DIGEST_LOG_FILE  = _cfg["rutas"]["digest_log_file"]

# ── Modelos, precios y matrices ──────────────────────────
MODELO_DEFAULT = _cfg["modelos"]["default"]
MODELO_DIGEST  = _cfg["modelos"]["digest"]
PRECIOS_USD    = {modelo: tuple(precios) for modelo, precios in _cfg["precios_usd"].items()}
MATRIZ_PATHS   = _cfg["matriz_paths"]

# ── Filtros de mails (digest diario) ─────────────────────
ASUNTOS_RUIDO   = tuple(_cfg["filtros"]["asuntos_ruido"])
MARCADORES_CITA = tuple(_cfg["filtros"]["marcadores_cita"])

# ── Memoria histórica ────────────────────────────────────
DIGESTS_HISTORICOS = _cfg.get("memoria", {}).get("digests_historicos", 14)

# ── Prompts ──────────────────────────────────────────────
# Los prompts se versionan en el repo (carpeta prompts/, junto al código),
# no en PM Agent. Ruta relativa al repo para que funcione en cualquier máquina.
PROMPTS_FOLDER = Path(__file__).with_name("prompts")

# ============================================================
#  PLANNER — NO mover a configuracion.toml.
#  Este bloque lo ESCRIBE automáticamente planner_client.py (por regex)
#  la primera vez que el bot se conecta a Planner. tomllib es solo-lectura,
#  así que debe seguir siendo un dict literal acá. No editar manualmente.
# ============================================================
PLANNER_PLANES = {
    "DevSecOps": "QNz1pTxlGkWflbBOgjeZbmQADnjD",
    "Programa Salesforce": "lmWVA6a6uEWMb6ks2z4Z0mQABVNT",
    "Monitoreo": "75EuHZ6p50iXx0jiDdU-cWQACWAY",
    "Obsolescencia": "nEj_feGLd0GvDeVGf4ZcDGQAAv-W",
    "WURU Finochietto": "AZ-lGAVN9kO0vDbGOe0WtWQAClXH"
}

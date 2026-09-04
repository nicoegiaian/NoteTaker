"""
jira_feed.py — Lee el feed de JIRA que un agente externo (ej. un agente programado
de Cowork) deja en OneDrive.

División de responsabilidades: el agente externo se conecta a JIRA (OAuth, sin
token) y ESCRIBE un archivo de texto con el rollup ejecutivo por programa; acá solo
se LEE. El razonamiento y el cruce con el cronograma los hace el digest — así el
"cerebro" queda en un solo lugar y el timing lo sigue mandando el gantt, no JIRA.
"""

from datetime import datetime, timedelta
from pathlib import Path

from config import JIRA_FEEDS, JIRA_FRESCURA_DIAS


def leer_jira(proyecto: str) -> str:
    """Feed de JIRA más reciente del proyecto (o '' si no hay o está viejo)."""
    carpeta = JIRA_FEEDS.get(proyecto)
    if not carpeta or not Path(carpeta).exists():
        return ""

    archivos = sorted(Path(carpeta).glob("*.txt"),
                      key=lambda f: f.stat().st_mtime, reverse=True)
    if not archivos:
        return ""

    ultimo = archivos[0]
    # Guardia de frescura: si el agente externo no corrió, el feed queda viejo.
    # Mejor omitir JIRA que mostrar datos rancios como si fueran de hoy.
    edad = datetime.now() - datetime.fromtimestamp(ultimo.stat().st_mtime)
    if edad > timedelta(days=JIRA_FRESCURA_DIAS):
        return ""

    try:
        return ultimo.read_text(encoding="utf-8").strip()
    except Exception:
        return ""

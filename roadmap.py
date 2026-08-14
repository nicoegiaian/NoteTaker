"""
roadmap.py — Cronograma del programa desde el export HTML del gantt (MS Project).

Para los proyectos con roadmap configurado (config.ROADMAPS: proyecto → carpeta),
toma el HTML más reciente de esa carpeta, extrae las tareas (nombre, ventana,
código WBS) y devuelve un cronograma compacto e indentado por jerarquía. El digest
lo usa como AUTORIDAD DEL CALENDARIO: valida la actividad/estado contra la ventana
planificada (quietud antes de la ventana = esperado, no riesgo), en vez de tirar
fruta mirando solo el estado de JIRA o la última actualización.
"""

import re
from pathlib import Path

from config import ROADMAPS, ROADMAP_MAX_DEPTH

# Cada tarea del gantt es un array JSON:
#   ["id","Sí","Programada …","<nombre>","<duración>","<inicio>","<fin>",<pred>,null,"<WBS>",…]
# Capturamos nombre, inicio (con año), fin (con año) y el código WBS (jerarquía).
_FILA = re.compile(
    r'\["[^"]*","[^"]*","[^"]*",'      # id, activo, modo de programación
    r'"([^"]*)",'                      # 1: nombre
    r'"[^"]*",'                        # duración (se ignora)
    r'"([^"]*20\d\d[^"]*)",'           # 2: inicio (contiene año)
    r'"([^"]*20\d\d[^"]*)"'            # 3: fin (contiene año)
    r'[^\]]*?"(DM\.[0-9.]+)"'          # 4: WBS
)


def _sin_hora(fecha: str) -> str:
    """'7 septiembre 2026 09:00' → '7 septiembre 2026'."""
    return re.sub(r"\s+\d{1,2}:\d{2}.*$", "", fecha).strip()


def _clave_wbs(wbs: str) -> tuple:
    """'DM.1.10' → (1, 10) para orden natural (no alfabético)."""
    return tuple(int(x) if x.isdigit() else 0 for x in wbs.split(".")[1:])


def _parsear(texto: str) -> dict:
    """Extrae las tareas del HTML: {WBS: (depth, nombre, inicio, fin)}. Dedup por
    WBS porque el array suele venir duplicado (panel + chart)."""
    filas = {}
    for m in _FILA.finditer(texto):
        wbs = m.group(4)
        if wbs in filas:
            continue
        depth = len(wbs.split("."))  # 'DM.1'=2, 'DM.1.5'=3 (módulo), 'DM.1.5.2'=4 (fase) …
        if depth > ROADMAP_MAX_DEPTH:
            continue
        nombre = m.group(1).strip().strip("​").strip()
        filas[wbs] = (depth, nombre, _sin_hora(m.group(2)), _sin_hora(m.group(3)))
    return filas


def leer_cronograma(proyecto: str) -> str:
    """Cronograma por módulo/fase del proyecto (o '' si no tiene roadmap).
    Toma el HTML más reciente de la carpeta que efectivamente parsee (la carpeta
    puede tener otros HTML de distinto formato que no traen las tareas)."""
    carpeta = ROADMAPS.get(proyecto)
    if not carpeta or not Path(carpeta).exists():
        return ""

    htmls = sorted(Path(carpeta).glob("*.html"),
                   key=lambda f: f.stat().st_mtime, reverse=True)

    fuente, filas = None, {}
    for html in htmls:
        try:
            f = _parsear(html.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if f:
            fuente, filas = html, f
            break

    if not filas:
        return ""

    lineas = []
    for wbs in sorted(filas, key=_clave_wbs):
        depth, nombre, ini, fin = filas[wbs]
        sangria = "  " * max(0, depth - 2)  # raíz(2)=0, módulo(3)=1, fase(4)=2 …
        if ini == fin:
            lineas.append(f"{sangria}- {nombre} · hito {ini}")
        else:
            lineas.append(f"{sangria}- {nombre}: {ini} → {fin}")

    return f"(Fuente: {fuente.name})\n" + "\n".join(lineas)

"""
glosario.py — Glosario de nombres propios por proyecto y normalización.

El glosario vive en la ficha del proyecto, en la sección protegida
'=== GLOSARIO / NOMBRES PROPIOS ==='. Cada línea es un nombre canónico, con
variantes mal escritas OPCIONALES tras una barra vertical:

    Api-Core | APICOR, APICORE, API-CORE
    CamDoctor | Campdoctor, Cam Doctor
    Motor de Reglas

Las variantes se reemplazan por su forma canónica (palabra completa, sin
importar mayúsculas) en la salida del digest y de las notas — un reemplazo
determinístico que no depende de que el LLM las corrija, y que corta el loop
de realimentación (la forma mala nunca se escribe de vuelta en la ficha).
"""

import re
from pathlib import Path
from config import CONTEXTO_FOLDER

_HEADER = "=== GLOSARIO / NOMBRES PROPIOS ==="


def leer_glosario(proyecto: str) -> str:
    """Texto crudo de la sección GLOSARIO de la ficha del proyecto ("" si no hay)."""
    ruta = Path(CONTEXTO_FOLDER) / f"contexto_{proyecto}.txt"
    if not ruta.exists():
        return ""
    try:
        texto = ruta.read_text(encoding="utf-8")
    except Exception:
        return ""
    i = texto.find(_HEADER)
    if i == -1:
        return ""
    resto = texto[i + len(_HEADER):]
    fin = resto.find("\n=== ")
    return (resto if fin == -1 else resto[:fin]).strip()


def _pares_variantes(glosario: str):
    """(variante, canónico) por cada variante declarada, más largas primero
    (para que 'APICORE' se reemplace antes que 'APICOR')."""
    pares = []
    for linea in glosario.splitlines():
        linea = linea.strip().lstrip("-•").strip()
        if not linea or "|" not in linea:
            continue
        canonico, _, resto = linea.partition("|")
        canonico = canonico.strip()
        if not canonico:
            continue
        # Unificar también la mayúscula/minúscula del propio canónico
        # (ej: "API-CORE" o "api-core" → "Api-Core").
        pares.append((canonico, canonico))
        for var in resto.split(","):
            var = var.strip()
            if var and var.lower() != canonico.lower():
                pares.append((var, canonico))
    pares.sort(key=lambda p: len(p[0]), reverse=True)
    return pares


def normalizar(texto: str, proyecto: str) -> str:
    """Reemplaza las variantes mal escritas del glosario por su forma canónica.
    Palabra completa (\\b) y case-insensitive; deja el resto del texto intacto."""
    if not texto:
        return texto
    for variante, canonico in _pares_variantes(leer_glosario(proyecto)):
        patron = re.compile(r"\b" + re.escape(variante) + r"\b", re.IGNORECASE)
        texto = patron.sub(canonico, texto)
    return texto

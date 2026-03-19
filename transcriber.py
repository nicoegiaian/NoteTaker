"""
transcriber.py — Parser de archivos .vtt de Teams
Reemplaza Whisper. Lee el transcript oficial de Microsoft,
que ya incluye texto limpio y nombres de participantes.
"""

import re
import logging
from pathlib import Path

log = logging.getLogger(__name__)


def transcribir_audio(ruta_archivo: str) -> str:
    """
    Lee un archivo .vtt de Teams y devuelve el transcript formateado.
    Mantiene el mismo nombre de función para no cambiar main.py.

    Args:
        ruta_archivo: Ruta al archivo .vtt descargado de Teams

    Returns:
        Texto completo con formato "Speaker: texto" por línea
    """
    ruta = Path(ruta_archivo)

    if ruta.suffix.lower() != ".vtt":
        raise ValueError(f"Se esperaba un .vtt pero se recibió: {ruta.suffix}")

    with open(ruta, "r", encoding="utf-8") as f:
        contenido = f.read()

    lineas = _parsear_vtt(contenido)

    if not lineas:
        raise ValueError("El archivo .vtt está vacío o no tiene el formato esperado.")

    # Unir líneas consecutivas del mismo speaker para mayor legibilidad
    lineas_agrupadas = _agrupar_por_speaker(lineas)

    transcript = "\n".join(lineas_agrupadas)

    log.info(f"   Participantes detectados: {', '.join(_extraer_participantes(lineas))}")

    return transcript


def _parsear_vtt(contenido: str) -> list[dict]:
    """
    Parsea el contenido del .vtt y extrae speaker + texto por segmento.
    
    El formato de Teams es:
    
    00:01:23.456 --> 00:01:27.890
    <v Nombre Apellido>texto que dijo</v>
    
    O sin tags de speaker:
    
    00:01:23.456 --> 00:01:27.890
    texto sin speaker
    """
    lineas = []

    # Separar por bloques (cada bloque tiene timestamp + texto)
    bloques = re.split(r'\n\n+', contenido.strip())

    for bloque in bloques:
        lineas_bloque = bloque.strip().splitlines()

        # Ignorar encabezado WEBVTT y bloques vacíos
        if not lineas_bloque or lineas_bloque[0].startswith("WEBVTT"):
            continue

        # Buscar línea de timestamp
        timestamp_linea = None
        texto_lineas = []

        for linea in lineas_bloque:
            if "-->" in linea:
                timestamp_linea = linea
            elif timestamp_linea and linea.strip() and not linea.strip().isdigit():
                texto_lineas.append(linea.strip())

        if not timestamp_linea or not texto_lineas:
            continue

        # Extraer tiempo de inicio
        tiempo_inicio = timestamp_linea.split("-->")[0].strip()
        tiempo_fmt    = _formatear_tiempo_vtt(tiempo_inicio)

        # Unir texto del bloque
        texto_completo = " ".join(texto_lineas)

        # Intentar extraer speaker del tag <v Nombre>
        match_speaker = re.match(r'<v ([^>]+)>(.*)', texto_completo, re.DOTALL)
        if match_speaker:
            speaker = match_speaker.group(1).strip()
            texto   = re.sub(r'</v>.*', '', match_speaker.group(2)).strip()
        else:
            # Sin tag de speaker — limpiar cualquier otro tag HTML
            speaker = "Participante"
            texto   = re.sub(r'<[^>]+>', '', texto_completo).strip()

        # Limpiar texto de tags residuales
        texto = re.sub(r'<[^>]+>', '', texto).strip()

        if texto:
            lineas.append({
                "tiempo":   tiempo_fmt,
                "speaker":  speaker,
                "texto":    texto,
            })

    return lineas


def _agrupar_por_speaker(lineas: list[dict]) -> list[str]:
    """
    Agrupa segmentos consecutivos del mismo speaker en una sola línea.
    Reduce el ruido y hace el transcript más legible para Claude.
    """
    if not lineas:
        return []

    resultado = []
    grupo_actual = lineas[0].copy()

    for linea in lineas[1:]:
        if linea["speaker"] == grupo_actual["speaker"]:
            grupo_actual["texto"] += " " + linea["texto"]
        else:
            resultado.append(f"[{grupo_actual['tiempo']}] {grupo_actual['speaker']}: {grupo_actual['texto']}")
            grupo_actual = linea.copy()

    # Agregar el último grupo
    resultado.append(f"[{grupo_actual['tiempo']}] {grupo_actual['speaker']}: {grupo_actual['texto']}")

    return resultado


def _extraer_participantes(lineas: list[dict]) -> list[str]:
    """Devuelve lista de participantes únicos detectados."""
    return sorted(set(l["speaker"] for l in lineas if l["speaker"] != "Participante"))


def _formatear_tiempo_vtt(tiempo: str) -> str:
    """
    Convierte timestamp VTT (00:01:23.456) a formato legible (01:23).
    """
    try:
        partes = tiempo.replace(",", ".").split(":")
        if len(partes) == 3:
            horas   = int(partes[0])
            minutos = int(partes[1])
            segs    = int(float(partes[2]))
            minutos_total = horas * 60 + minutos
            return f"{minutos_total:02d}:{segs:02d}"
    except Exception:
        pass
    return tiempo.split(".")[0]

"""
notificaciones.py — Notificaciones de Windows
Muestra alertas en la esquina inferior derecha del escritorio.
"""

import logging

log = logging.getLogger(__name__)

APP_NAME = "NoteTaker Bot"

def _notificar(titulo: str, mensaje: str, duracion: int = 8):
    """Muestra una notificación de Windows. Falla silenciosamente si no está disponible."""
    try:
        from plyer import notification
        notification.notify(
            title=titulo,
            message=mensaje,
            app_name=APP_NAME,
            timeout=duracion,
        )
    except Exception as e:
        # Si plyer no está disponible o falla, solo logueamos
        log.warning(f"No se pudo mostrar notificacion: {e}")


def nueva_grabacion_disponible(nombre_reunion: str):
    """Alerta cuando aparece un nuevo .mp4 en Recordings sin .vtt procesado."""
    _notificar(
        titulo="Nueva grabacion de Teams",
        mensaje=f"Descarga el .vtt de:\n{nombre_reunion}",
        duracion=10,
    )


def archivo_duplicado(nombre_archivo: str, fecha_original: str):
    """Alerta cuando se intenta procesar un archivo ya procesado."""
    _notificar(
        titulo="Archivo ya procesado",
        mensaje=f"{nombre_archivo}\nYa fue procesado el {fecha_original}",
        duracion=8,
    )


def minuta_lista(nombre_reunion: str, proyecto: str):
    """Alerta cuando se genera una minuta exitosamente."""
    _notificar(
        titulo=f"Minuta lista - {proyecto}",
        mensaje=f"{nombre_reunion}\nAbri la carpeta Minutas para verla.",
        duracion=8,
    )


def error_procesamiento(nombre_archivo: str, error: str):
    """Alerta cuando falla el procesamiento de un archivo."""
    _notificar(
        titulo="Error en NoteTaker",
        mensaje=f"No se pudo procesar:\n{nombre_archivo[:50]}",
        duracion=8,
    )

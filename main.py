"""
main.py — Orquestador principal
Monitorea DOS carpetas:
  1. Downloads  -> detecta .vtt nuevos y los MUEVE a Recordings
  2. Recordings -> detecta .vtt y los procesa (genera notas HTML)
"""
from dotenv import load_dotenv
load_dotenv()

import os
import sys
import time
import shutil
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from config import ESPERA_SINCRONIZACION_SEG
from transcriber import transcribir_audio
from ai_processor import generar_notas
from output_generator import guardar_html

# Encoding para Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Configuracion de logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("meeting_notes.log", encoding="utf-8"),
    ]
)
log = logging.getLogger(__name__)

# Cargar configuracion
RECORDINGS_PATH = os.getenv("ONEDRIVE_RECORDINGS_PATH")
OUTPUT_FOLDER   = os.getenv("OUTPUT_FOLDER")
DOWNLOADS_PATH  = os.getenv(
    "DOWNLOADS_PATH",
    str(Path.home() / "Downloads")
)


def procesar_grabacion(ruta_archivo: str):
    """Pipeline: .vtt -> transcript -> notas -> HTML"""
    nombre = Path(ruta_archivo).name
    log.info(f"Procesando: {nombre}")

    try:
        log.info("   Leyendo transcript del .vtt...")
        transcript = transcribir_audio(ruta_archivo)
        palabras = len(transcript.split())
        log.info(f"   Transcript listo: {palabras} palabras")

        log.info("   Generando notas con IA...")
        notas = generar_notas(transcript, nombre)
        log.info("   Notas generadas")

        log.info("   Guardando HTML...")
        ruta_output = guardar_html(notas, nombre, OUTPUT_FOLDER)
        log.info(f"   LISTO: {ruta_output}")
        log.info(f"   Abri ese archivo, hace clic en Copiar y pega en Loop")

    except Exception as e:
        log.error(f"   Error procesando {nombre}: {e}")
        raise


class WatcherDownloads(FileSystemEventHandler):
    """
    Monitorea la carpeta Downloads.
    Maneja tanto on_created como on_moved porque los navegadores
    descargan a un archivo temporal y luego lo renombran al .vtt final.
    """

    def __init__(self):
        self.en_proceso = set()

    def _mover_a_recordings(self, ruta: str):
        if ruta in self.en_proceso:
            return
        if Path(ruta).suffix.lower() != ".vtt":
            return

        self.en_proceso.add(ruta)
        nombre = Path(ruta).name
        log.info(f"[Downloads] .vtt detectado: {nombre}")

        time.sleep(3)

        if not os.path.exists(ruta) or os.path.getsize(ruta) < 100:
            log.warning("   Archivo no disponible o vacio, ignorando.")
            self.en_proceso.discard(ruta)
            return

        destino = os.path.join(RECORDINGS_PATH, nombre)
        if os.path.exists(destino):
            stem = Path(nombre).stem
            suffix = Path(nombre).suffix
            timestamp = time.strftime("%H%M%S")
            destino = os.path.join(RECORDINGS_PATH, f"{stem}_{timestamp}{suffix}")

        log.info(f"   Moviendo a: '{destino}'")
        try:
            shutil.move(ruta, destino)
            log.info(f"   Movido OK: {Path(destino).name}")
        except Exception as e:
            log.error(f"   Error al mover: {e}")

        self.en_proceso.discard(ruta)

    def on_created(self, event):
        if not event.is_directory:
            self._mover_a_recordings(event.src_path)

    def on_moved(self, event):
        # El navegador renombra el .crdownload/.tmp al .vtt final
        if not event.is_directory:
            self._mover_a_recordings(event.dest_path)

class WatcherRecordings(FileSystemEventHandler):
    """
    Monitorea la carpeta Recordings.
    Cuando detecta un .vtt lo procesa y genera el HTML.
    """

    def __init__(self):
        self.en_proceso = set()

    def on_created(self, event):
        if event.is_directory:
            return

        ruta = event.src_path
        if Path(ruta).suffix.lower() != ".vtt":
            return
        if ruta in self.en_proceso:
            return

        self.en_proceso.add(ruta)
        nombre = Path(ruta).name
        log.info(f"[Recordings] .vtt listo para procesar: {nombre}")

        time.sleep(ESPERA_SINCRONIZACION_SEG)

        if not os.path.exists(ruta) or os.path.getsize(ruta) < 100:
            log.warning("   Archivo no disponible o vacio, ignorando.")
            self.en_proceso.discard(ruta)
            return

        procesar_grabacion(ruta)
        self.en_proceso.discard(ruta)


def main():
    if not RECORDINGS_PATH or not os.path.exists(RECORDINGS_PATH):
        log.error(f"No se encuentra la carpeta Recordings: '{RECORDINGS_PATH}'")
        log.error("Verifica ONEDRIVE_RECORDINGS_PATH en el archivo .env")
        return

    if not os.path.exists(DOWNLOADS_PATH):
        log.error(f"No se encuentra la carpeta Downloads: '{DOWNLOADS_PATH}'")
        log.error("Verifica DOWNLOADS_PATH en el archivo .env")
        return

    if not os.getenv("GEMINI_API_KEY"):
        log.error("No se encontro GEMINI_API_KEY en el archivo .env")
        return

    Path(OUTPUT_FOLDER).mkdir(parents=True, exist_ok=True)

    log.info("=" * 55)
    log.info("  Meeting Notes Bot - Iniciado")
    log.info(f"  Escuchando Downloads:  {DOWNLOADS_PATH}")
    log.info(f"  Procesando en:         {RECORDINGS_PATH}")
    log.info(f"  Notas HTML en:         {OUTPUT_FOLDER}")
    log.info("  Flujo: descargar .vtt de Teams -> se mueve solo -> notas listas")
    log.info("  Para detener: Ctrl + C")
    log.info("=" * 55)

    observer = Observer()
    observer.schedule(WatcherDownloads(), DOWNLOADS_PATH, recursive=False)
    observer.schedule(WatcherRecordings(), RECORDINGS_PATH, recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        observer.stop()
        log.info("Bot detenido.")
    observer.join()


if __name__ == "__main__":
    main()

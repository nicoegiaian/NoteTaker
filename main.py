"""
main.py — Orquestador principal
Monitorea la carpeta de OneDrive y procesa nuevas grabaciones automáticamente.
Ejecutar con: python main.py
"""

import os
import time
import logging
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from config import ESPERA_SINCRONIZACION_SEG
from transcriber import transcribir_audio
from ai_processor import generar_notas
from output_generator import guardar_html

# ── Configuración de logs ─────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),                        # muestra en pantalla
        logging.FileHandler("meeting_notes.log"),       # guarda en archivo
    ]
)
log = logging.getLogger(__name__)

# ── Cargar credenciales ───────────────────────────────────
load_dotenv()
RECORDINGS_PATH = os.getenv("ONEDRIVE_RECORDINGS_PATH")
OUTPUT_FOLDER   = os.getenv("OUTPUT_FOLDER")

# ── Extensiones de video a monitorear ────────────────────
EXTENSIONES_VIDEO = {".mp4", ".mov", ".mkv", ".webm"}


def procesar_grabacion(ruta_archivo: str):
    """Pipeline completo: audio → transcripción → notas → HTML"""
    nombre = Path(ruta_archivo).name
    log.info(f"▶  Procesando: {nombre}")

    try:
        # Paso 1 — Transcribir audio con Whisper
        log.info("   🎙  Transcribiendo audio (puede tardar varios minutos)...")
        transcript = transcribir_audio(ruta_archivo)
        log.info(f"   ✓  Transcripción completa ({len(transcript.split())} palabras)")

        # Paso 2 — Generar notas con Claude
        log.info("   🤖  Generando notas con IA...")
        notas = generar_notas(transcript, nombre)
        log.info("   ✓  Notas generadas")

        # Paso 3 — Guardar HTML
        log.info("   💾  Guardando archivo HTML...")
        ruta_output = guardar_html(notas, nombre, OUTPUT_FOLDER)
        log.info(f"   ✅  Listo: {ruta_output}")
        log.info(f"   📋  Abrí ese archivo, copiá todo y pegalo en Loop")

    except Exception as e:
        log.error(f"   ❌  Error procesando {nombre}: {e}")
        raise


class WatcherGrabaciones(FileSystemEventHandler):
    """Detecta archivos de video nuevos en la carpeta monitoreada"""

    def __init__(self):
        self.en_proceso = set()   # evita procesar el mismo archivo dos veces

    def on_created(self, event):
        if event.is_directory:
            return
        ruta = event.src_path
        ext  = Path(ruta).suffix.lower()

        if ext not in EXTENSIONES_VIDEO:
            return
        if ruta in self.en_proceso:
            return

        self.en_proceso.add(ruta)
        nombre = Path(ruta).name
        log.info(f"📥  Nueva grabación detectada: {nombre}")
        log.info(f"   ⏳  Esperando {ESPERA_SINCRONIZACION_SEG}s a que termine la sincronización...")

        # Esperar a que OneDrive termine de sincronizar el archivo
        time.sleep(ESPERA_SINCRONIZACION_SEG)

        # Verificar que el archivo sigue ahí y tiene tamaño razonable
        if not os.path.exists(ruta) or os.path.getsize(ruta) < 1_000_000:
            log.warning(f"   ⚠️  Archivo no disponible o muy pequeño, ignorando.")
            self.en_proceso.discard(ruta)
            return

        procesar_grabacion(ruta)
        self.en_proceso.discard(ruta)


def main():
    # Verificar configuración
    if not RECORDINGS_PATH or not os.path.exists(RECORDINGS_PATH):
        log.error(f"❌  No se encuentra la carpeta de grabaciones: {RECORDINGS_PATH}")
        log.error("   Verificá la variable ONEDRIVE_RECORDINGS_PATH en el archivo .env")
        return

    if not os.getenv("ANTHROPIC_API_KEY"):
        log.error("❌  No se encontró ANTHROPIC_API_KEY en el archivo .env")
        return

    # Crear carpeta de output si no existe
    Path(OUTPUT_FOLDER).mkdir(parents=True, exist_ok=True)

    log.info("=" * 55)
    log.info("  🚀  Meeting Notes Bot — Iniciado")
    log.info(f"  📁  Monitoreando: {RECORDINGS_PATH}")
    log.info(f"  💾  Output en:    {OUTPUT_FOLDER}")
    log.info("  Para detener: Ctrl + C")
    log.info("=" * 55)

    handler  = WatcherGrabaciones()
    observer = Observer()
    observer.schedule(handler, RECORDINGS_PATH, recursive=True)
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

"""
main.py — Orquestador principal
Monitorea TRES carpetas/eventos:
  1. Downloads  -> detecta .vtt nuevos y los MUEVE a Recordings
  2. Recordings -> detecta .vtt y los procesa (genera notas HTML)
  3. Recordings -> detecta .mp4 nuevos y avisa que hay que bajar el .vtt
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
from datetime import datetime


# Agregar ffmpeg al PATH
os.environ["PATH"] += r";C:\Users\degiaian\ffmpeg\bin"

from config import ESPERA_SINCRONIZACION_SEG
from transcriber import transcribir_audio
from ai_processor import generar_notas
from gemini_processor import es_minuta_gemini, procesar_minuta_gemini
from output_generator import guardar_html
from registro import ya_procesado, marcar_procesado, obtener_info
from notificaciones import (
    nueva_grabacion_disponible,
    archivo_duplicado,
    minuta_lista,
    error_procesamiento,
)
from proyecto_watcher import encolar_archivo, digest_todos_los_proyectos, digest_ya_corrido_hoy, PROYECTOS
from f3_analisis_minuta import analizar_minuta_cruzada


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


def procesar_grabacion(ruta_archivo: str, tipo_forzado: str = None):
    """Pipeline: .vtt -> transcript -> notas -> HTML"""
    from transcriber import extraer_uuid_vtt, duracion_minutos_vtt
    nombre  = Path(ruta_archivo).name
    carpeta = Path(ruta_archivo).parent

    # Verificar duración mínima — ignorar grabaciones fallidas
    duracion = duracion_minutos_vtt(ruta_archivo)
    if duracion < 2:
        log.warning(f"Ignorando '{nombre}' — grabación muy corta ({duracion:.1f} min), probablemente fallida")
        return

    # Verificar duplicado
    if not tipo_forzado and ya_procesado(nombre):
        info  = obtener_info(nombre)
        fecha = info.get("procesado_el", "fecha desconocida")
        log.warning(f"DUPLICADO: '{nombre}' ya fue procesado el {fecha}")
        archivo_duplicado(nombre, fecha)
        return

    log.info(f"Procesando: {nombre} ({duracion:.1f} min)")

    try:
        # Detectar si hay partes adicionales (mismo UUID, distinto archivo)
        uuid_actual = extraer_uuid_vtt(ruta_archivo)
        stem        = Path(ruta_archivo).stem
        transcripts = []

        # Buscar archivos con el mismo nombre base + sufijo _algo
        archivos_relacionados = sorted(carpeta.glob(f"{stem}_*.vtt"))
        partes_mismo_uuid = []
        for f in archivos_relacionados:
            if extraer_uuid_vtt(str(f)) == uuid_actual:
                partes_mismo_uuid.append(f)

        log.info("   Leyendo transcript del .vtt...")
        transcripts.append(transcribir_audio(ruta_archivo))

        if partes_mismo_uuid:
            for parte in partes_mismo_uuid:
                log.info(f"   Fusionando parte: {parte.name}")
                transcripts.append(transcribir_audio(str(parte)))
            transcript = "\n\n--- CONTINUACION ---\n\n".join(transcripts)
            log.info(f"   Transcript fusionado: {len(transcripts)} partes")
        else:
            transcript = transcripts[0]

        palabras = len(transcript.split())
        log.info(f"   Transcript listo: {palabras} palabras")

        log.info("   Generando notas con IA...")
        notas = generar_notas(transcript, nombre, tipo_forzado=tipo_forzado)
        log.info("   Notas generadas")

        log.info("   Guardando HTML...")
        ruta_output = guardar_html(notas, nombre, OUTPUT_FOLDER)
        log.info(f"   LISTO: {ruta_output}")

        marcar_procesado(nombre, ruta_output)

        # Crear tareas en Planner
        # F3 — Análisis cruzado antes de crear tareas en Planner
        proyecto = notas.get("proyecto", "")
        log.info("   Iniciando análisis cruzado F3...")
        try:
            analizar_minuta_cruzada(notas, nombre, ruta_output, OUTPUT_FOLDER)
        except Exception as ef3:
            log.warning(f"   F3 no disponible: {ef3}")

        # Crear tareas en Planner
        acciones = notas.get("acciones", [])
        if acciones and proyecto and proyecto != "Sin Proyecto Asignado":
            try:
                from planner_client import crear_tareas_en_planner
                titulo_reunion = notas.get("titulo", nombre)
                resultado_planner = crear_tareas_en_planner(acciones, proyecto, titulo_reunion)
                log.info(f"   Planner: {resultado_planner}")
            except Exception as ep:
                log.warning(f"   Planner no disponible: {ep}")


    except Exception as e:
        log.error(f"   Error procesando {nombre}: {e}")
        error_procesamiento(nombre, str(e))
        raise

class WatcherDownloads(FileSystemEventHandler):
    """
    Monitorea Downloads.
    Maneja on_created y on_moved porque los navegadores
    descargan a archivo temporal y luego lo renombran al .vtt final.
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
        if not event.is_directory:
            self._mover_a_recordings(event.dest_path)


class WatcherRecordings(FileSystemEventHandler):
    """
    Monitorea Recordings.
    - .vtt nuevos: los procesa y genera HTML
    - .mp4 nuevos: avisa que hay que descargar el .vtt
    """

    def __init__(self):
        self.en_proceso = set()
        # Esperar 30 min antes de avisar por el .mp4
        # (Teams tarda en generar la transcripcion)
        self.ESPERA_MP4_SEG = 1800

    def on_created(self, event):
        if event.is_directory:
            return

        ruta = event.src_path
        ext  = Path(ruta).suffix.lower()
        nombre = Path(ruta).name

        if ext == ".vtt":
            self._procesar_vtt(ruta)
        elif ext == ".mp4":
            self._avisar_mp4(ruta)
        elif ext == ".docx" and es_minuta_gemini(nombre):
            self._procesar_docx_gemini(ruta)

    def _procesar_vtt(self, ruta: str):
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

    def _avisar_mp4(self, ruta: str):
        """
        Cuando aparece un .mp4 nuevo, espera 30 minutos y luego
        verifica si ya fue procesado el .vtt correspondiente.
        Si no fue procesado, manda una notificacion recordatorio.
        """
        import threading

        nombre_mp4  = Path(ruta).name
        # El .vtt de Teams tiene el mismo nombre que el .mp4
        nombre_vtt  = Path(ruta).stem + ".vtt"

        def _chequear_despues():
            log.info(f"[Recordings] Nuevo .mp4 detectado: {nombre_mp4}")
            log.info(f"   Esperando {self.ESPERA_MP4_SEG//60} min para verificar si se proceso el .vtt...")
            time.sleep(self.ESPERA_MP4_SEG)

            if ya_procesado(nombre_vtt):
                log.info(f"   .vtt ya procesado para: {nombre_mp4} - sin notificacion")
            else:
                log.info(f"   .vtt pendiente para: {nombre_mp4} - enviando recordatorio")
                # Limpiar el nombre para la notificacion
                nombre_limpio = Path(nombre_mp4).stem
                nombre_limpio = nombre_limpio.replace("-20", " -20")  # separar fecha
                nueva_grabacion_disponible(nombre_limpio)

        # Correr en thread separado para no bloquear el watcher
        t = threading.Thread(target=_chequear_despues, daemon=True)
        t.start()

    def _procesar_docx_gemini(self, ruta: str):
        if ruta in self.en_proceso:
            return

        self.en_proceso.add(ruta)
        nombre = Path(ruta).name
        log.info(f"[Recordings] .docx Gemini detectado: {nombre}")
        time.sleep(5)

        if not os.path.exists(ruta) or os.path.getsize(ruta) < 100:
            log.warning("   Archivo no disponible, ignorando.")
            self.en_proceso.discard(ruta)
            return

        try:
            notas = procesar_minuta_gemini(ruta)
            if not notas:
                self.en_proceso.discard(ruta)
                return

            # Mismo pipeline que el .vtt desde guardar_html en adelante
            ruta_output = guardar_html(notas, nombre, OUTPUT_FOLDER)
            log.info(f"   HTML generado: {ruta_output}")

            marcar_procesado(nombre, ruta_output)
    
            # F3 análisis cruzado
            log.info("   Iniciando análisis cruzado F3...")
            try:
                from f3_analisis_minuta import analizar_minuta_cruzada
                analizar_minuta_cruzada(notas, nombre, ruta_output, OUTPUT_FOLDER)
            except Exception as ef3:
                log.warning(f"   F3 no disponible: {ef3}")

            # Crear tareas en Planner
            acciones = notas.get("acciones", [])
            proyecto = notas.get("proyecto", "")
            if acciones and proyecto and proyecto != "Sin Proyecto Asignado":
                try:
                    from planner_client import crear_tareas_en_planner
                    titulo_reunion = notas.get("titulo", nombre)
                    resultado_planner = crear_tareas_en_planner(acciones, proyecto, titulo_reunion)
                    log.info(f"   Planner: {resultado_planner}")
                except Exception as ep:
                    log.warning(f"   Planner no disponible: {ep}")

        except Exception as e:
            log.error(f"   Error procesando {nombre}: {e}")
        finally:
            self.en_proceso.discard(ruta)

class WatcherProyectos(FileSystemEventHandler):
    """
    Monitorea las carpetas de proyectos en SharePoint local.
    Detecta archivos nuevos o modificados y los procesa con F1b.
    """

    EXTENSIONES = {".docx", ".pdf", ".xlsx", ".xls"}
    ESPERA_SEG  = 10

    def __init__(self):
        self.en_proceso = set()
        self.ultimo_procesado = {}

    def _procesar(self, ruta: str, evento: str):
        if ruta in self.en_proceso:
            return
        if Path(ruta).suffix.lower() not in self.EXTENSIONES:
            return
        if Path(ruta).name.startswith("~$"):
            return

        ahora = time.time()
        ultimo = self.ultimo_procesado.get(ruta, 0)
        if ahora - ultimo < 60:
            log.info(f"[WatcherProyectos] Ignorando evento duplicado: {Path(ruta).name}")
            return

        self.en_proceso.add(ruta)
        self.ultimo_procesado[ruta] = ahora
        time.sleep(self.ESPERA_SEG)

        if not os.path.exists(ruta) or os.path.getsize(ruta) < 100:
            self.en_proceso.discard(ruta)
            return

        try:
            encolar_archivo(ruta, evento)
        except Exception as e:
            log.error(f"[WatcherProyectos] Error: {e}")

        self.en_proceso.discard(ruta)

    def on_created(self, event):
        if not event.is_directory:
            self._procesar(event.src_path, "subió")

    def on_modified(self, event):
        if not event.is_directory:
            self._procesar(event.src_path, "modificó")


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

    # Verificar autorizacion de Microsoft para Planner
    try:
        from auth_microsoft import esta_autorizado, obtener_token
        if not esta_autorizado():
            log.info("Planner: primera vez — iniciando autorizacion de Microsoft...")
            obtener_token()  # lanza Device Code Flow interactivo
        else:
            log.info("Planner: credenciales guardadas OK")
    except Exception as e:
        log.warning(f"Planner no disponible: {e}")

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

    import threading

    # ── Hilo del agente de chat ──────────────────────────────────────────────
    def _hilo_chat():
        try:
            from agente_chat import iniciar_server
            iniciar_server()  # bloquea en su propio thread, daemon=True
        except Exception as e:
            log.error(f"Agente de chat no pudo iniciarse: {e}")
 
    hilo_chat = threading.Thread(target=_hilo_chat, daemon=True)
    hilo_chat.start()
    log.info("  Agente de chat: http://localhost:8765")
    # ────────────────────────────────────────────────────────────────────────

    # ── Hilo del digest diario  ──────────────────────────────────────────────

    def _hilo_digest():
        import time as _time
        # Al arrancar: correr si ya son las 9am y no corrió hoy
        if datetime.now().hour >= 9 and not digest_ya_corrido_hoy():
            log.info("Digest pendiente al arrancar, ejecutando...")
            digest_todos_los_proyectos()
        # Chequear cada hora
        while True:
            _time.sleep(3600)
            if datetime.now().hour >= 9 and not digest_ya_corrido_hoy():
                digest_todos_los_proyectos()

    hilo = threading.Thread(target=_hilo_digest, daemon=True)
    hilo.start()

    for carpeta_proyecto in PROYECTOS.keys():
        if os.path.exists(carpeta_proyecto):
            observer.schedule(WatcherProyectos(), carpeta_proyecto, recursive=True)
            log.info(f"  Monitoreando proyecto: {PROYECTOS[carpeta_proyecto]}")
        else:
            log.warning(f"  Carpeta no encontrada: {carpeta_proyecto}")
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        observer.stop()
        log.info("Bot detenido.")
    observer.join()


if __name__ == "__main__":
    main()

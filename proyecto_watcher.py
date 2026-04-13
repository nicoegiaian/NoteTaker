"""
proyecto_watcher.py — F1b: Monitoreo y digest diario de archivos de proyectos
"""

import os
import json
import logging
import requests
import urllib3
from pathlib import Path
from datetime import datetime, date

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
log = logging.getLogger(__name__)

# ─── CONFIGURACIÓN ────────────────────────────────────────
PROYECTOS = {
    r"C:\Users\degiaian\OneDrive - ASE Conecta\CORPO - Gerencia de Proyectos Corporativos - Proyectos en curso\DevSecOps": "DevSecOps",
    r"C:\Users\degiaian\OneDrive - ASE Conecta\CORPO - Gerencia de Proyectos Corporativos - Proyectos en curso\Monitoreo": "Monitoreo",
    r"C:\Users\degiaian\OneDrive - ASE Conecta\CORPO - Gerencia de Proyectos Corporativos - Proyectos en curso\Salesforce HealthCloud": "Salesforce HealthCloud",
    r"C:\Users\degiaian\OneDrive - ASE Conecta\CORPO - Seguridad-SI e INFRA - Obsolescencia": "Obsolescencia",
}

EXTENSIONES_SOPORTADAS = {".docx", ".pdf", ".xlsx", ".xls"}
CONTEXTO_FOLDER  = r"C:\Users\degiaian\OneDrive - ASE Conecta\Documentos\PMO\PM Agent"
NOVEDADES_FOLDER = r"C:\Users\degiaian\OneDrive - ASE Conecta\Documentos\PMO\PM Agent\Novedades_de_archivos"
COLA_FILE        = r"C:\Users\degiaian\OneDrive - ASE Conecta\Documentos\PMO\PM Agent\cola_archivos.json"
DIGEST_LOG_FILE  = r"C:\Users\degiaian\OneDrive - ASE Conecta\Documentos\PMO\PM Agent\digest_log.json"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"


# ─── COLA ─────────────────────────────────────────────────
def cargar_cola() -> dict:
    if Path(COLA_FILE).exists():
        try:
            return json.loads(Path(COLA_FILE).read_text(encoding="utf-8"))
        except Exception:
            pass
    return {nombre: [] for nombre in PROYECTOS.values()}


def guardar_cola(cola: dict):
    Path(COLA_FILE).write_text(
        json.dumps(cola, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def encolar_archivo(ruta: str, evento: str):
    """Agrega un archivo a la cola del proyecto correspondiente."""
    proyecto = detectar_proyecto(ruta)
    if not proyecto:
        return
    if Path(ruta).suffix.lower() not in EXTENSIONES_SOPORTADAS:
        return
    if Path(ruta).name.startswith("~$"):
        return

    cola = cargar_cola()
    if proyecto not in cola:
        cola[proyecto] = []

    # Evitar duplicados de la misma ruta
    rutas_existentes = [item["ruta"] for item in cola[proyecto]]
    if ruta in rutas_existentes:
        # Actualizar evento si ya existe
        for item in cola[proyecto]:
            if item["ruta"] == ruta:
                item["evento"] = evento
                item["timestamp"] = datetime.now().isoformat()
        log.info(f"[Cola] Actualizado: {Path(ruta).name} → {proyecto}")
    else:
        cola[proyecto].append({
            "ruta": ruta,
            "nombre": Path(ruta).name,
            "evento": evento,
            "timestamp": datetime.now().isoformat(),
        })
        log.info(f"[Cola] Encolado: {Path(ruta).name} → {proyecto}")

    guardar_cola(cola)


# ─── DIGEST LOG ───────────────────────────────────────────
def cargar_digest_log() -> dict:
    if Path(DIGEST_LOG_FILE).exists():
        try:
            return json.loads(Path(DIGEST_LOG_FILE).read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def guardar_digest_log(log_data: dict):
    Path(DIGEST_LOG_FILE).write_text(
        json.dumps(log_data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def marcar_digest_ejecutado():
    log_data = cargar_digest_log()
    log_data["ultima_ejecucion"] = datetime.now().isoformat()
    guardar_digest_log(log_data)

def digest_ya_corrido_hoy() -> bool:
    log_data = cargar_digest_log()
    ultima = log_data.get("ultima_ejecucion", "")
    if not ultima:
        return False
    try:
        ultima_dt = datetime.fromisoformat(ultima)
        return ultima_dt.date() == date.today()
    except Exception:
        return False


# ─── LECTURA DE ARCHIVOS ──────────────────────────────────
def detectar_proyecto(ruta: str) -> str | None:
    for carpeta_proyecto, nombre_proyecto in PROYECTOS.items():
        if ruta.startswith(carpeta_proyecto):
            return nombre_proyecto
    return None


def leer_word(ruta: str) -> str:
    from docx import Document
    doc = Document(ruta)
    texto = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
    return texto[:8000]


def leer_pdf(ruta: str) -> str:
    import pdfplumber
    with pdfplumber.open(ruta) as pdf:
        texto = ""
        for page in pdf.pages[:5]:
            texto += page.extract_text() or ""
    return texto[:8000]


def leer_excel(ruta: str) -> str:
    from openpyxl import load_workbook
    wb = load_workbook(ruta, data_only=True)
    resultado = []
    for nombre_hoja in wb.sheetnames[:3]:
        ws = wb[nombre_hoja]
        filas = []
        for row in list(ws.iter_rows(values_only=True))[:30]:
            fila = [str(c) for c in row if c is not None]
            if fila:
                filas.append(" | ".join(fila))
        if filas:
            resultado.append(f"[Hoja: {nombre_hoja}]\n" + "\n".join(filas))
    return "\n\n".join(resultado)[:8000]


def leer_contenido(ruta: str) -> str | None:
    ext = Path(ruta).suffix.lower()
    try:
        if ext == ".docx":
            return leer_word(ruta)
        elif ext == ".pdf":
            return leer_pdf(ruta)
        elif ext in {".xlsx", ".xls"}:
            return leer_excel(ruta)
    except Exception as e:
        log.error(f"Error leyendo {ruta}: {e}")
    return None


# ─── CONTEXTO ─────────────────────────────────────────────
def cargar_contexto(proyecto: str) -> str:
    ruta = Path(CONTEXTO_FOLDER) / f"contexto_{proyecto}.txt"
    if ruta.exists():
        return ruta.read_text(encoding="utf-8")
    return "Sin contexto previo disponible."


def guardar_contexto(proyecto: str, nuevo_contexto: str):
    ruta = Path(CONTEXTO_FOLDER) / f"contexto_{proyecto}.txt"
    ruta.write_text(nuevo_contexto, encoding="utf-8")
    log.info(f"Contexto actualizado: {ruta.name}")


# ─── CLAUDE API ───────────────────────────────────────────
def llamar_claude(prompt: str) -> dict:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 2500,
        "messages": [{"role": "user", "content": prompt}],
    }
    resp = requests.post(
        ANTHROPIC_API_URL,
        headers=headers,
        json=payload,
        verify=False,
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    return {
        "texto": data["content"][0]["text"],
        "input_tokens": data["usage"]["input_tokens"],
        "output_tokens": data["usage"]["output_tokens"],
    }


# ─── TOKENS ───────────────────────────────────────────────
def registrar_tokens(proyecto: str, funcion: str, input_tokens: int, output_tokens: int):
    try:
        from openpyxl import load_workbook
        ruta = Path(CONTEXTO_FOLDER) / "PM_Agent_Registro.xlsx"
        wb = load_workbook(ruta)
        ws = wb.active
        costo = (input_tokens * 0.0000008) + (output_tokens * 0.000004)
        ws.append([
            datetime.now().strftime("%d/%m/%Y %H:%M"),
            proyecto,
            funcion,
            input_tokens,
            output_tokens,
            round(costo, 6),
        ])
        wb.save(ruta)
    except Exception as e:
        log.warning(f"No se pudo registrar tokens: {e}")


# ─── NOVEDADES ────────────────────────────────────────────
def escribir_novedad(proyecto: str, mensaje: str, sufijo: str):
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre = f"{proyecto}_{timestamp}_{sufijo}.txt"
        ruta = Path(NOVEDADES_FOLDER) / nombre
        ruta.write_text(mensaje, encoding="utf-8")
        log.info(f"   Novedad escrita: {nombre}")
    except Exception as e:
        log.error(f"Error escribiendo novedad: {e}")


# ─── DIGEST ───────────────────────────────────────────────
def digest_proyecto(proyecto: str, items: list):
    """Procesa la cola de un proyecto y genera el digest."""
    if not items:
        log.info(f"[Digest] Sin archivos encolados para {proyecto}")
        return

    log.info(f"[Digest] Procesando {len(items)} archivos para {proyecto}")

    contenidos = []
    for item in items:
        ruta = item["ruta"]
        nombre = item["nombre"]
        evento = item["evento"]

        if not Path(ruta).exists():
            log.warning(f"   Archivo no encontrado, ignorando: {nombre}")
            continue

        contenido = leer_contenido(ruta)
        if contenido and len(contenido.strip()) > 50:
            contenidos.append(f"--- ARCHIVO: {nombre} ({evento}) ---\n{contenido}")
        else:
            contenidos.append(f"--- ARCHIVO: {nombre} ({evento}) ---\n[Contenido no legible]")

    if not contenidos:
        log.info(f"[Digest] Sin contenido legible para {proyecto}")
        return

    contexto_actual = cargar_contexto(proyecto)
    contenido_archivos = "\n\n".join(contenidos)

    prompt = f"""Sos un asistente experto en gestión de proyectos. A continuación te comparto los archivos que fueron creados o modificados ayer en el proyecto "{proyecto}".

CONTEXTO ACTUAL DEL PROYECTO:
{contexto_actual}

ARCHIVOS DEL DÍA:
{contenido_archivos}

Analizá todos los archivos en conjunto y respondé en español con este formato exacto:

📅 DIGEST DE ARCHIVOS — {proyecto}
📁 Archivos procesados: {len(contenidos)}

📋 RESUMEN DEL DÍA:
[Resumen consolidado de todos los cambios y novedades, relacionando archivos si corresponde]

🔄 IMPACTO EN EL PROYECTO:
[Qué cambia o se agrega al proyecto con estos documentos]

⚠️ ALERTAS:
[Temas fuera de alcance, riesgos nuevos, cambios importantes. Si no hay: 'Sin alertas.']

✅ TAREAS SUGERIDAS:
[Lista numerada de acciones concretas sugeridas. Si no aplica: 'Sin tareas sugeridas.']

📌 CONTEXTO ACTUALIZADO DEL PROYECTO:
[Si los archivos representan cambios significativos al contexto, reescribilo incorporando la nueva información. Si no hay cambios importantes, escribí exactamente: SIN_CAMBIOS]"""

    resultado = llamar_claude(prompt)
    texto_completo = resultado["texto"]

    # Separar digest del contexto actualizado
    partes = texto_completo.split("📌 CONTEXTO ACTUALIZADO DEL PROYECTO:")
    digest = partes[0].strip()

    if len(partes) > 1:
        nuevo_contexto = partes[1].strip()
        if nuevo_contexto != "SIN_CAMBIOS":
            guardar_contexto(proyecto, nuevo_contexto)
            log.info(f"   Contexto actualizado para {proyecto}")

    escribir_novedad(proyecto, digest, "digest_archivos")
    registrar_tokens(proyecto, "Digest_Archivos", resultado["input_tokens"], resultado["output_tokens"])
    log.info(f"[Digest] Completado para {proyecto}")


def digest_todos_los_proyectos():
    """Corre el digest para todos los proyectos procesando todo lo acumulado hasta ayer."""
    if digest_ya_corrido_hoy():
        log.info("[Digest] Ya se corrió hoy, saltando.")
        return

    log.info("[Digest] Iniciando digest diario de archivos...")
    cola = cargar_cola()

    hoy_inicio = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    for proyecto in PROYECTOS.values():
        items_a_procesar = []
        items_restantes = []

        for item in cola.get(proyecto, []):
            try:
                ts = datetime.fromisoformat(item["timestamp"])
                if ts < hoy_inicio:
                    items_a_procesar.append(item)
                else:
                    items_restantes.append(item)
            except Exception:
                items_restantes.append(item)

        cola[proyecto] = items_restantes

        try:
            digest_proyecto(proyecto, items_a_procesar)
        except Exception as e:
            log.error(f"[Digest] Error en {proyecto}: {e}")

    guardar_cola(cola)
    marcar_digest_ejecutado()
    log.info("[Digest] Digest diario completado.")
"""
proyecto_watcher.py — F1b: Monitoreo y digest diario de archivos de proyectos
"""

import os
import json
import logging
import requests
import urllib3
from pathlib import Path
from datetime import datetime, date, timedelta

from config import PROYECTOS as PROYECTOS_KEYWORDS

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
log = logging.getLogger(__name__)

# ─── CONFIGURACIÓN ────────────────────────────────────────
PROYECTOS = {
    r"C:\Users\degiaian\OneDrive - ASE Conecta\CORPO - Gerencia de Proyectos Corporativos - Proyectos en curso\DevSecOps": "DevSecOps",
    r"C:\Users\degiaian\OneDrive - ASE Conecta\CORPO - Gerencia de Proyectos Corporativos - Proyectos en curso\Monitoreo": "Monitoreo",
    r"C:\Users\degiaian\OneDrive - ASE Conecta\CORPO - Gerencia de Proyectos Corporativos - Proyectos en curso\Salesforce HealthCloud": "Programa Salesforce",
    r"C:\Users\degiaian\OneDrive - ASE Conecta\CORPO - Seguridad-SI e INFRA - Obsolescencia": "Obsolescencia",
}

EXTENSIONES_SOPORTADAS = {".docx", ".pdf", ".xlsx", ".xls"}
CONTEXTO_FOLDER  = r"C:\Users\degiaian\OneDrive - ASE Conecta\Documentos\PMO\PM Agent"
NOVEDADES_FOLDER = r"C:\Users\degiaian\OneDrive - ASE Conecta\Documentos\PMO\PM Agent\Novedades_de_archivos"
MAILS_FOLDER     = r"C:\Users\degiaian\OneDrive - ASE Conecta\Documentos\PMO\PM Agent\Mails_del_dia"
COLA_FILE        = r"C:\Users\degiaian\OneDrive - ASE Conecta\Documentos\PMO\PM Agent\cola_archivos.json"
DIGEST_LOG_FILE  = r"C:\Users\degiaian\OneDrive - ASE Conecta\Documentos\PMO\PM Agent\digest_log.json"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"

# ─── MODELOS ──────────────────────────────────────────────
# Haiku para ingesta/extracción de alto volumen (F3, digest de archivos legacy).
# Sonnet para el razonamiento del digest diario (puntos ciegos, síntesis).
# Para máxima calidad, cambiar MODELO_DIGEST a "claude-opus-4-8".
MODELO_DEFAULT = "claude-haiku-4-5-20251001"
MODELO_DIGEST  = "claude-sonnet-5"

# Precio USD por token (entrada, salida). Sonnet 5 usa tarifa estándar
# (durante el intro hasta 2026-08-31 el costo real es menor).
_PRECIOS_USD = {
    "claude-haiku-4-5-20251001": (0.000001, 0.000005),
    "claude-sonnet-5":           (0.000003, 0.000015),
    "claude-opus-4-8":           (0.000005, 0.000025),
}


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


def proyectos_procesados_hoy() -> set:
    """Retorna el set de proyectos ya procesados hoy."""
    log_data = cargar_digest_log()
    ultima = log_data.get("fecha", "")
    try:
        if datetime.fromisoformat(ultima).date() == date.today():
            return set(log_data.get("proyectos_ok", []))
    except Exception:
        pass
    return set()

def proyectos_procesados_hoy() -> set:
    """Retorna el set de proyectos ya procesados hoy."""
    log_data = cargar_digest_log()
    ultima = log_data.get("fecha", "")
    try:
        if datetime.fromisoformat(ultima).date() == date.today():
            return set(log_data.get("proyectos_ok", []))
    except Exception:
        pass
    return set()


def marcar_proyecto_procesado(proyecto: str):
    """Marca un proyecto como procesado exitosamente hoy."""
    log_data = cargar_digest_log()
    fecha_actual = date.today().isoformat()

    # Si cambió el día, resetear
    try:
        if log_data.get("fecha", "") != fecha_actual:
            log_data = {"fecha": fecha_actual, "proyectos_ok": []}
    except Exception:
        log_data = {"fecha": fecha_actual, "proyectos_ok": []}

    if proyecto not in log_data.get("proyectos_ok", []):
        log_data.setdefault("proyectos_ok", []).append(proyecto)

    log_data["ultima_ejecucion"] = datetime.now().isoformat()
    guardar_digest_log(log_data)


def digest_ya_corrido_hoy() -> bool:
    """El digest está completo si todos los proyectos fueron procesados hoy."""
    procesados = proyectos_procesados_hoy()
    todos = set(PROYECTOS.values())
    return todos.issubset(procesados)


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


def guardar_contexto(proyecto: str, contenido_agente: str):
    """
    Actualiza solo las secciones del agente en el contexto del proyecto.
    Nunca toca las secciones escritas por el PM:
    DESCRIPCIÓN Y ALCANCE, EQUIPO CLAVE, HITOS VIGENTES, RIESGOS IDENTIFICADOS.
    """
    ruta = Path(CONTEXTO_FOLDER) / f"contexto_{proyecto}.txt"
    
    # Secciones protegidas — escritas por el PM
    SECCIONES_PROTEGIDAS = [
        "=== DESCRIPCIÓN Y ALCANCE ===",
        "=== EQUIPO CLAVE ===",
        "=== HITOS VIGENTES ===",
        "=== RIESGOS IDENTIFICADOS ===",
    ]
    
    # Secciones del agente — se actualizan automáticamente
    SECCIONES_AGENTE = [
        "=== ESTADO ACTUAL ===",
        "=== DECISIONES TOMADAS ===",
    ]

    if ruta.exists():
        contenido_actual = ruta.read_text(encoding="utf-8")
    else:
        contenido_actual = ""

    # Verificar si el archivo tiene la estructura esperada
    tiene_estructura = any(s in contenido_actual for s in SECCIONES_PROTEGIDAS)

    if not tiene_estructura:
        # Archivo sin estructura → escribir todo (comportamiento anterior)
        ruta.write_text(contenido_agente, encoding="utf-8")
        log.info(f"Contexto creado: {ruta.name}")
        return

    # Extraer la parte protegida (todo hasta la primera sección del agente)
    primera_seccion_agente = None
    pos_corte = len(contenido_actual)
    for seccion in SECCIONES_AGENTE:
        pos = contenido_actual.find(seccion)
        if pos != -1 and pos < pos_corte:
            pos_corte = pos
            primera_seccion_agente = seccion

    parte_protegida = contenido_actual[:pos_corte].rstrip()

    # Parsear el contenido nuevo del agente para extraer estado y decisiones
    estado_nuevo = ""
    decisiones_nuevas = ""

    if "=== ESTADO ACTUAL ===" in contenido_agente:
        partes = contenido_agente.split("=== ESTADO ACTUAL ===")
        if len(partes) > 1:
            resto = partes[1]
            if "=== DECISIONES TOMADAS ===" in resto:
                estado_nuevo = resto.split("=== DECISIONES TOMADAS ===")[0].strip()
            else:
                estado_nuevo = resto.strip()

    if "=== DECISIONES TOMADAS ===" in contenido_agente:
        partes = contenido_agente.split("=== DECISIONES TOMADAS ===")
        if len(partes) > 1:
            decisiones_nuevas = partes[1].strip()

    # Si el agente no devolvió secciones estructuradas, preservar las existentes
    if not estado_nuevo:
        if "=== ESTADO ACTUAL ===" in contenido_actual:
            partes = contenido_actual.split("=== ESTADO ACTUAL ===")
            resto = partes[1] if len(partes) > 1 else ""
            if "=== DECISIONES TOMADAS ===" in resto:
                estado_nuevo = resto.split("=== DECISIONES TOMADAS ===")[0].strip()
            else:
                estado_nuevo = resto.strip()

    if not decisiones_nuevas:
        if "=== DECISIONES TOMADAS ===" in contenido_actual:
            partes = contenido_actual.split("=== DECISIONES TOMADAS ===")
            decisiones_nuevas = partes[1].strip() if len(partes) > 1 else ""

    # Reconstruir el archivo completo
    nuevo_contenido = f"""{parte_protegida}

=== ESTADO ACTUAL ===
{estado_nuevo}

=== DECISIONES TOMADAS ===
{decisiones_nuevas}
"""
    ruta.write_text(nuevo_contenido, encoding="utf-8")
    log.info(f"Contexto actualizado (secciones protegidas intactas): {ruta.name}")



# ─── CLAUDE API ───────────────────────────────────────────
def llamar_claude(prompt: str, modelo: str = MODELO_DEFAULT, sin_pensar: bool = False) -> dict:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": modelo,
        "max_tokens": 2500,
        "messages": [{"role": "user", "content": prompt}],
    }
    # Sonnet 5 trae thinking adaptativo por defecto; lo desactivamos para el digest
    # (salida y costo predecibles, sin que el thinking consuma el presupuesto de tokens).
    if sin_pensar:
        payload["thinking"] = {"type": "disabled"}

    resp = requests.post(
        ANTHROPIC_API_URL,
        headers=headers,
        json=payload,
        verify=False,
        timeout=90,
    )
    resp.raise_for_status()
    data = resp.json()

    # Extraer el primer bloque de texto (puede haber bloques 'thinking' antes)
    texto = next((b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"), "")

    return {
        "texto": texto,
        "input_tokens": data["usage"]["input_tokens"],
        "output_tokens": data["usage"]["output_tokens"],
    }


# ─── TOKENS ───────────────────────────────────────────────
def registrar_tokens(proyecto: str, funcion: str, input_tokens: int, output_tokens: int,
                     modelo: str = MODELO_DEFAULT):
    try:
        from openpyxl import load_workbook
        ruta = Path(CONTEXTO_FOLDER) / "PM_Agent_Registro.xlsx"
        wb = load_workbook(ruta)
        ws = wb.active
        precio_in, precio_out = _PRECIOS_USD.get(modelo, _PRECIOS_USD[MODELO_DEFAULT])
        costo = (input_tokens * precio_in) + (output_tokens * precio_out)
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


# ─── FUENTES DEL DIGEST DIARIO ────────────────────────────
def _detectar_proyecto_por_nombre(nombre: str) -> str | None:
    """Detecta el proyecto por palabra clave en el nombre de archivo (minutas)."""
    nombre_lower = nombre.lower()
    for clave, proyecto in PROYECTOS_KEYWORDS.items():
        if clave.lower() in nombre_lower:
            return proyecto
    return None


def leer_mails_del_dia(proyecto: str) -> str:
    """Lee el archivo de mails que Power Automate dejó hoy para el proyecto."""
    fecha = date.today().strftime("%Y%m%d")
    ruta = Path(MAILS_FOLDER) / f"{proyecto}_{fecha}.txt"
    if not ruta.exists():
        return ""
    try:
        return ruta.read_text(encoding="utf-8").strip()
    except Exception as e:
        log.warning(f"[Digest] No se pudo leer mails de {proyecto}: {e}")
        return ""


def _html_a_texto(ruta: str, limite: int = 3000) -> str:
    """Extrae texto plano de una minuta HTML."""
    from bs4 import BeautifulSoup
    try:
        contenido = Path(ruta).read_text(encoding="utf-8")
        soup = BeautifulSoup(contenido, "html.parser")
        return soup.get_text(separator="\n", strip=True)[:limite]
    except Exception as e:
        log.warning(f"[Digest] No se pudo leer minuta {Path(ruta).name}: {e}")
        return ""


def leer_reuniones_recientes(proyecto: str, desde: datetime, maximo: int = 5) -> str:
    """Junta el texto de las minutas (HTML) del proyecto generadas desde `desde`."""
    output = os.getenv("OUTPUT_FOLDER", "")
    if not output or not Path(output).exists():
        return ""

    partes = []
    htmls = sorted(Path(output).glob("*.html"), key=lambda f: f.stat().st_mtime, reverse=True)
    for html in htmls:
        if _detectar_proyecto_por_nombre(html.name) != proyecto:
            continue
        if datetime.fromtimestamp(html.stat().st_mtime) < desde:
            continue
        texto = _html_a_texto(str(html))
        if texto:
            fecha = datetime.fromtimestamp(html.stat().st_mtime).strftime("%d/%m/%Y")
            partes.append(f"--- REUNIÓN {fecha}: {html.name} ---\n{texto}")
        if len(partes) >= maximo:
            break

    return "\n\n".join(partes)


def _cutoff_reuniones() -> datetime:
    """Desde cuándo juntar reuniones: última ejecución del digest, o 3 días atrás."""
    log_data = cargar_digest_log()
    try:
        return datetime.fromisoformat(log_data.get("ultima_ejecucion", ""))
    except Exception:
        return datetime.now() - timedelta(days=3)


# ─── DIGEST ───────────────────────────────────────────────
def digest_proyecto(proyecto: str, items: list, cutoff_reuniones: datetime):
    """Genera el digest diario unificado del proyecto: mails + reuniones + archivos."""
    # 1. Archivos modificados (cola de F1b)
    contenidos = []
    for item in items:
        ruta   = item["ruta"]
        nombre = item["nombre"]
        evento = item["evento"]
        if not Path(ruta).exists():
            log.warning(f"   Archivo no encontrado, ignorando: {nombre}")
            continue
        contenido = leer_contenido(ruta)
        if contenido and len(contenido.strip()) > 50:
            contenidos.append(f"--- ARCHIVO: {nombre} ({evento}) ---\n{contenido}")
    texto_archivos = "\n\n".join(contenidos) if contenidos else "Sin archivos modificados."

    # 2. Mails de ayer (los dejó Power Automate)
    texto_mails = leer_mails_del_dia(proyecto)

    # 3. Reuniones recientes (minutas generadas desde la última corrida)
    texto_reuniones = leer_reuniones_recientes(proyecto, cutoff_reuniones)

    # Decidir si hay algo que reportar
    hay_mails     = bool(texto_mails) and texto_mails.strip() not in ("", "[]")
    hay_reuniones = bool(texto_reuniones)
    hay_archivos  = bool(contenidos)
    if not (hay_mails or hay_reuniones or hay_archivos):
        log.info(f"[Digest] {proyecto}: sin novedades ayer, no se genera digest.")
        return

    log.info(f"[Digest] {proyecto} | mails: {hay_mails} | reuniones: {hay_reuniones} | archivos: {len(contenidos)}")

    contexto_actual = cargar_contexto(proyecto)

    prompt_path = Path(CONTEXTO_FOLDER) / "Prompts" / "prompt_digest_diario.txt"
    try:
        prompt_template = prompt_path.read_text(encoding="utf-8")
    except Exception as e:
        log.error(f"No se pudo leer prompt diario: {e}")
        return

    prompt = (prompt_template
              .replace("{{PROYECTO}}",   proyecto)
              .replace("{{FECHA}}",      date.today().strftime("%d/%m/%Y"))
              .replace("{{CONTEXTO}}",   contexto_actual)
              .replace("{{MAILS}}",      texto_mails or "Sin mails.")
              .replace("{{REUNIONES}}",  texto_reuniones or "Sin reuniones.")
              .replace("{{ARCHIVOS}}",   texto_archivos))

    resultado = llamar_claude(prompt, modelo=MODELO_DIGEST, sin_pensar=True)
    texto_completo = resultado["texto"]

    # Separar digest del contexto actualizado
    partes = texto_completo.split("📌 CONTEXTO ACTUALIZADO DEL PROYECTO:")
    digest = partes[0].strip()

    if len(partes) > 1:
        nuevo_contexto = partes[1].strip()
        if nuevo_contexto and nuevo_contexto != "SIN_CAMBIOS":
            guardar_contexto(proyecto, nuevo_contexto)
            log.info(f"   Contexto actualizado para {proyecto}")

    escribir_novedad(proyecto, digest, "digest_diario")
    registrar_tokens(proyecto, "Digest_Diario", resultado["input_tokens"], resultado["output_tokens"],
                     modelo=MODELO_DIGEST)
    log.info(f"[Digest] Diario completado para {proyecto} (modelo: {MODELO_DIGEST})")


def digest_todos_los_proyectos():
    """Corre el digest diario unificado solo para proyectos pendientes."""
    if digest_ya_corrido_hoy():
        log.info("[Digest] Ya se corrió hoy para todos los proyectos, saltando.")
        return

    log.info("[Digest] Iniciando digest diario unificado...")
    cutoff_reuniones = _cutoff_reuniones()  # capturar antes de marcar proyectos
    cola = cargar_cola()
    ya_procesados = proyectos_procesados_hoy()

    hoy_inicio = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    for proyecto in PROYECTOS.values():
        if proyecto in ya_procesados:
            log.info(f"[Digest] {proyecto} ya procesado hoy, saltando.")
            continue

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

        try:
            digest_proyecto(proyecto, items_a_procesar, cutoff_reuniones)
            # Solo limpiar la cola y marcar si fue exitoso
            cola[proyecto] = items_restantes
            marcar_proyecto_procesado(proyecto)
        except Exception as e:
            log.error(f"[Digest] Error en {proyecto}: {e}")
            # No limpia cola ni marca, se reintenta en la próxima hora

    guardar_cola(cola)
    log.info("[Digest] Digest diario completado.")
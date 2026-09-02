"""
agente_chat.py — Agente conversacional local
Corre en localhost:8765 como parte del proceso principal.

GET  /           → UI del chat
GET  /proyectos  → lista de proyectos disponibles
POST /chat       → consulta al agente (two-pass: selección + respuesta)
POST /crear-tareas → crear tareas en Planner (compatibilidad con HTMLs existentes)
POST /reprocesar   → reprocesa un transcript forzando el tipo de reunión
POST /enviar-mail  → guarda ediciones de una minuta y abre el borrador en Outlook
"""

import os
import re
import json
import logging
import requests
import urllib3
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from datetime import datetime

from config import PROYECTOS

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
log = logging.getLogger(__name__)

ANTHROPIC_API_URL  = "https://api.anthropic.com/v1/messages"
MAX_VTT_CHARS      = 12_000
MAX_HTML_CHARS     = 3_000
MAX_VTTS_FALLBACK  = 5
MAX_HTMLS_FALLBACK = 5


# ─── PROYECTOS ──────────────────────────────────────────────────────────────
def _proyectos_unicos() -> list[str]:
    return sorted(set(PROYECTOS.values()))


def _detectar_proyecto_archivo(nombre: str) -> str | None:
    nombre_lower = nombre.lower()
    for clave, proyecto in PROYECTOS.items():
        if clave.lower() in nombre_lower:
            return proyecto
    return None


# ─── LISTADO DE ARCHIVOS ────────────────────────────────────────────────────
def _listar_vtts(proyecto: str) -> list[dict]:
    recordings = os.getenv("ONEDRIVE_RECORDINGS_PATH", "")
    if not recordings or not Path(recordings).exists():
        return []

    resultado = []
    for vtt in Path(recordings).glob("*.vtt"):
        if _detectar_proyecto_archivo(vtt.name) != proyecto:
            continue
        fecha = datetime.fromtimestamp(vtt.stat().st_mtime)
        resultado.append({
            "ruta":      str(vtt),
            "nombre":    vtt.name,
            "fecha":     fecha,
            "fecha_str": fecha.strftime("%Y-%m-%d"),
            "tipo":      "vtt",
        })
    return sorted(resultado, key=lambda x: x["fecha"], reverse=True)


def _listar_htmls(proyecto: str) -> list[dict]:
    output = os.getenv("OUTPUT_FOLDER", "")
    if not output or not Path(output).exists():
        return []

    resultado = []
    for html in Path(output).glob("*.html"):
        if _detectar_proyecto_archivo(html.name) != proyecto:
            continue
        try:
            fecha = datetime.strptime(html.name[:13], "%Y%m%d_%H%M")
        except Exception:
            fecha = datetime.fromtimestamp(html.stat().st_mtime)
        resultado.append({
            "ruta":      str(html),
            "nombre":    html.name,
            "fecha":     fecha,
            "fecha_str": fecha.strftime("%Y-%m-%d"),
            "tipo":      "html",
        })
    return sorted(resultado, key=lambda x: x["fecha"], reverse=True)


# ─── ÍNDICE ─────────────────────────────────────────────────────────────────
def _armar_indice(vtts: list[dict], htmls: list[dict]) -> tuple[str, list[dict]]:
    """Retorna (texto del índice para Claude, lista completa ordenada)."""
    todos  = vtts + htmls
    lineas = []
    for i, item in enumerate(todos, 1):
        tipo_label = "transcript" if item["tipo"] == "vtt" else "minuta"
        lineas.append(f"[{i}] {item['fecha_str']} | {item['nombre']} ({tipo_label})")
    return "\n".join(lineas), todos


# ─── PASO 1: SELECCIÓN DE ARCHIVOS RELEVANTES ───────────────────────────────
def _seleccionar_relevantes(pregunta: str, indice: str, todos: list[dict]) -> tuple[list[dict], int, int]:
    """Retorna (archivos seleccionados, input_tokens, output_tokens)."""
    api_key = os.getenv("ANTHROPIC_API_KEY")

    prompt = f"""Tenés este índice de transcripts de reuniones y minutas:

{indice}

El usuario pregunta: "{pregunta}"

¿Cuáles de estos archivos son relevantes para responder?
- Si la pregunta refiere a reuniones específicas (por nombre, fecha o tema concreto): \
respondé los números entre corchetes separados por coma. Ejemplo: [1],[3],[7]
- OJO CON LAS FECHAS: la fecha del índice es cuándo se GENERÓ la minuta/transcript, \
casi siempre el mismo día de la reunión o 1–3 días DESPUÉS (nunca antes). Por eso, \
cuando el usuario pide la reunión de una fecha, el archivo correcto puede figurar con \
una fecha algo POSTERIOR. Incluí los archivos cuya fecha sea IGUAL o hasta 3 días MAYOR \
a la fecha pedida. EJEMPLO CONCRETO: si el usuario pide "la reunión del 11 de agosto" y \
la minuta más cercana del mismo tema figura como "2026-08-12", ES ESA — INCLUILA \
(se generó al día siguiente). Ante la duda con la fecha, incluí de más.
- Matcheá también por TEMA y NOMBRE del archivo, no solo por fecha: si un archivo \
coincide por tema aunque la fecha no calce exacto, incluilo.
- Si la pregunta es general y aplica buscar en las más recientes: respondé RECIENTES
- Si ningún archivo parece relevante: respondé NINGUNO

Respondé SOLO con los números, RECIENTES o NINGUNO. Sin explicación adicional."""

    headers = {
        "x-api-key":         api_key,
        "anthropic-version": "2023-06-01",
        "content-type":      "application/json",
    }
    payload = {
        "model":      "claude-haiku-4-5-20251001",
        "max_tokens": 50,
        "messages":   [{"role": "user", "content": prompt}],
    }

    input_tokens = output_tokens = 0

    try:
        resp = requests.post(
            ANTHROPIC_API_URL, headers=headers, json=payload, verify=False, timeout=20
        )
        resp.raise_for_status()
        data          = resp.json()
        texto         = data["content"][0]["text"].strip()
        input_tokens  = data.get("usage", {}).get("input_tokens", 0)
        output_tokens = data.get("usage", {}).get("output_tokens", 0)
    except Exception as e:
        log.warning(f"[Chat] Error en selección de archivos, usando RECIENTES: {e}")
        texto = "RECIENTES"

    if texto == "NINGUNO":
        return [], input_tokens, output_tokens

    if texto == "RECIENTES":
        vtts  = [a for a in todos if a["tipo"] == "vtt"][:MAX_VTTS_FALLBACK]
        htmls = [a for a in todos if a["tipo"] == "html"][:MAX_HTMLS_FALLBACK]
        return vtts + htmls, input_tokens, output_tokens

    indices = [int(n) for n in re.findall(r'\d+', texto)]
    seleccionados = [todos[i - 1] for i in indices if 1 <= i <= len(todos)]
    log.info(f"[Chat] Paso 1 — archivos seleccionados: {[a['nombre'] for a in seleccionados]}")
    return seleccionados, input_tokens, output_tokens



# ─── LECTURA DE CONTENIDO ───────────────────────────────────────────────────
def _leer_archivo(item: dict) -> str:
    try:
        if item["tipo"] == "vtt":
            try:
                from transcriber import transcribir_audio
                return transcribir_audio(item["ruta"])[:MAX_VTT_CHARS]
            except Exception:
                return Path(item["ruta"]).read_text(encoding="utf-8")[:MAX_VTT_CHARS]

        elif item["tipo"] == "html":
            from bs4 import BeautifulSoup
            contenido = Path(item["ruta"]).read_text(encoding="utf-8")
            soup = BeautifulSoup(contenido, "html.parser")
            return soup.get_text(separator="\n", strip=True)[:MAX_HTML_CHARS]

    except Exception as e:
        log.error(f"[Chat] Error leyendo {item['nombre']}: {e}")
        return f"[Error leyendo {item['nombre']}]"
    return ""


def _armar_contexto(archivos: list[dict]) -> str:
    partes = []
    for item in archivos:
        contenido   = _leer_archivo(item)
        tipo_label  = "TRANSCRIPT" if item["tipo"] == "vtt" else "MINUTA"
        partes.append(
            f"=== {tipo_label}: {item['nombre']} ({item['fecha_str']}) ===\n{contenido}"
        )
    return "\n\n".join(partes)


# ─── PASO 2: RESPUESTA ──────────────────────────────────────────────────────
def _responder(pregunta: str, contexto: str, historial: list, contexto_proyecto: str = "") -> tuple[str, int, int]:
    """Retorna (respuesta, input_tokens, output_tokens)."""
    api_key = os.getenv("ANTHROPIC_API_KEY")

    system = (
        "Sos un asistente de gestión de proyectos que conoce a fondo el proyecto sobre el que te preguntan. "
        "Contás con dos fuentes: (1) la FICHA DEL PROYECTO —alcance, equipo, hitos, riesgos, estado actual y "
        "decisiones tomadas, mantenida al día— que es tu conocimiento de base sobre el proyecto; y (2) las "
        "FUENTES —transcripts y minutas de reuniones concretas—. "
        "Usá la ficha para entender el contexto y responder sobre el estado, alcance, riesgos o historia del proyecto. "
        "Cuando afirmes algo puntual que se dijo o decidió en una reunión, citá el archivo y la fecha de la fuente. "
        "Si algo no está ni en la ficha ni en las fuentes, decilo claramente — no inventes datos. "
        "Respondé en español, de forma concisa y directa."
    )

    bloques = []
    if contexto_proyecto:
        bloques.append(f"=== FICHA DEL PROYECTO ===\n{contexto_proyecto}")
    if contexto:
        bloques.append(f"=== FUENTES (transcripts y minutas) ===\n{contexto}")
    contexto_completo = "\n\n".join(bloques) if bloques else "Sin información disponible."

    messages = historial + [{
        "role":    "user",
        "content": f"{contexto_completo}\n\n---\nPregunta: {pregunta}",
    }]

    headers = {
        "x-api-key":         api_key,
        "anthropic-version": "2023-06-01",
        "content-type":      "application/json",
    }
    payload = {
        "model":     "claude-haiku-4-5-20251001",
        "max_tokens": 1000,
        "system":    system,
        "messages":  messages,
    }

    resp = requests.post(
        ANTHROPIC_API_URL, headers=headers, json=payload, verify=False, timeout=60
    )
    resp.raise_for_status()

    data          = resp.json()
    input_tokens  = data.get("usage", {}).get("input_tokens", 0)
    output_tokens = data.get("usage", {}).get("output_tokens", 0)

    log.info(f"[Chat] Tokens — entrada: {input_tokens}, salida: {output_tokens}")
    return data["content"][0]["text"], input_tokens, output_tokens


# ─── PIPELINE COMPLETO ──────────────────────────────────────────────────────
def procesar_consulta(pregunta: str, proyecto: str, historial: list) -> dict:
    # Ficha del proyecto (alcance, equipo, hitos, riesgos, estado, decisiones),
    # mantenida por F3 y el digest de archivos. Es el conocimiento de base del agente.
    from proyecto_watcher import cargar_contexto, registrar_tokens
    contexto_proyecto = cargar_contexto(proyecto)
    tiene_ficha = bool(contexto_proyecto) and contexto_proyecto != "Sin contexto previo disponible."

    vtts  = _listar_vtts(proyecto)
    htmls = _listar_htmls(proyecto)

    if not vtts and not htmls and not tiene_ficha:
        return {
            "respuesta":       f"No encontré información para el proyecto '{proyecto}'.",
            "archivos_usados": [],
        }

    log.info(f"[Chat] Proyecto: {proyecto} | VTTs: {len(vtts)} | HTMLs: {len(htmls)} | ficha: {tiene_ficha}")

    # Paso 1 — selección de archivos relevantes (solo si hay archivos)
    archivos_relevantes, tok_in1, tok_out1 = [], 0, 0
    if vtts or htmls:
        indice, todos = _armar_indice(vtts, htmls)
        archivos_relevantes, tok_in1, tok_out1 = _seleccionar_relevantes(pregunta, indice, todos)

    # Sin archivos relevantes ni ficha no hay con qué responder
    if not archivos_relevantes and not tiene_ficha:
        return {
            "respuesta": (
                "No encontré archivos relevantes para tu pregunta. "
                "Podés ser más específico sobre la reunión, el tema o la fecha."
            ),
            "archivos_usados": [],
        }

    # Paso 2 — respuesta con la ficha como base + las fuentes específicas seleccionadas
    contexto                     = _armar_contexto(archivos_relevantes) if archivos_relevantes else ""
    respuesta, tok_in2, tok_out2 = _responder(
        pregunta, contexto, historial, contexto_proyecto if tiene_ficha else ""
    )

    # Registrar tokens acumulados de ambos pasos
    try:
        registrar_tokens(proyecto, "Chat_Consulta", tok_in1 + tok_in2, tok_out1 + tok_out2)
    except Exception as e:
        log.warning(f"[Chat] No se pudo registrar tokens: {e}")

    return {
        "respuesta":       respuesta,
        "archivos_usados": [
            f"{a['nombre']} ({a['fecha_str']})" for a in archivos_relevantes
        ],
    }


# ─── HTML DE LA UI ──────────────────────────────────────────────────────────
CHAT_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PM Agent</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --bg:        #0f1117;
      --surface:   #181c27;
      --border:    #252a38;
      --accent:    #4f7cff;
      --accent-dim:#2a3f80;
      --text:      #e4e8f0;
      --text-dim:  #6b7494;
      --text-muted:#3d4460;
      --user-bg:   #1e2540;
      --agent-bg:  #181c27;
      --tag-bg:    #1a1f30;
      --tag-border:#2a3050;
    }

    html, body {
      height: 100%;
      font-family: 'DM Sans', sans-serif;
      background: var(--bg);
      color: var(--text);
      overflow: hidden;
    }

    /* ── Layout ── */
    .shell {
      display: grid;
      grid-template-columns: 260px 1fr;
      grid-template-rows: 100vh;
      height: 100vh;
    }

    /* ── Sidebar ── */
    .sidebar {
      background: var(--surface);
      border-right: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      padding: 28px 20px 24px;
      gap: 32px;
    }

    .logo {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .logo-icon {
      width: 36px; height: 36px;
      background: var(--accent);
      border-radius: 10px;
      display: flex; align-items: center; justify-content: center;
      font-size: 18px;
      flex-shrink: 0;
    }

    .logo-text { font-size: 15px; font-weight: 600; color: var(--text); }
    .logo-sub  { font-size: 11px; color: var(--text-dim); margin-top: 1px; }

    .sidebar-section { display: flex; flex-direction: column; gap: 8px; }

    .sidebar-label {
      font-size: 10px;
      font-weight: 600;
      letter-spacing: 1px;
      text-transform: uppercase;
      color: var(--text-muted);
      padding: 0 4px;
    }

    .proyecto-select {
      width: 100%;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      color: var(--text);
      font-family: 'DM Sans', sans-serif;
      font-size: 13px;
      padding: 9px 12px;
      cursor: pointer;
      outline: none;
      transition: border-color .15s;
    }
    .proyecto-select:focus { border-color: var(--accent); }
    .proyecto-select option { background: #1a1f30; }

    .new-chat-btn {
      width: 100%;
      padding: 10px;
      background: transparent;
      border: 1px dashed var(--border);
      border-radius: 8px;
      color: var(--text-dim);
      font-family: 'DM Sans', sans-serif;
      font-size: 13px;
      cursor: pointer;
      transition: all .15s;
      display: flex; align-items: center; justify-content: center; gap: 6px;
    }
    .new-chat-btn:hover {
      border-color: var(--accent);
      color: var(--accent);
      background: var(--accent-dim);
    }

    .tips {
      margin-top: auto;
      background: var(--tag-bg);
      border: 1px solid var(--tag-border);
      border-radius: 10px;
      padding: 14px;
    }
    .tips-title { font-size: 11px; font-weight: 600; color: var(--text-dim); margin-bottom: 10px; }
    .tips-item  {
      font-size: 12px;
      color: var(--text-dim);
      line-height: 1.5;
      padding: 4px 0;
      border-bottom: 1px solid var(--border);
    }
    .tips-item:last-child { border-bottom: none; }
    .tips-item em { color: var(--accent); font-style: normal; }

    /* ── Chat area ── */
    .chat-area {
      display: flex;
      flex-direction: column;
      min-height: 0;
    }

    .chat-header {
      padding: 18px 28px;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      gap: 12px;
      flex-shrink: 0;
    }
    .chat-header-title { font-size: 14px; font-weight: 600; color: var(--text); }
    .chat-header-sub   { font-size: 12px; color: var(--text-dim); }
    .status-dot {
      width: 8px; height: 8px;
      border-radius: 50%;
      background: #22c55e;
      flex-shrink: 0;
      box-shadow: 0 0 6px #22c55e88;
    }

    .messages {
      flex: 1;
      overflow-y: auto;
      padding: 32px 28px;
      display: flex;
      flex-direction: column;
      gap: 24px;
      scrollbar-width: thin;
      scrollbar-color: var(--border) transparent;
    }

    .empty-state {
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 16px;
      color: var(--text-muted);
      text-align: center;
    }
    .empty-icon  { font-size: 48px; opacity: .4; }
    .empty-title { font-size: 16px; color: var(--text-dim); font-weight: 500; }
    .empty-sub   { font-size: 13px; line-height: 1.8; }

    /* ── Messages ── */
    .msg-row { display: flex; gap: 12px; max-width: 760px; }
    .msg-row.user { align-self: flex-end; flex-direction: row-reverse; }

    .msg-avatar {
      width: 32px; height: 32px;
      border-radius: 8px;
      display: flex; align-items: center; justify-content: center;
      font-size: 14px;
      flex-shrink: 0;
      margin-top: 2px;
    }
    .msg-avatar.agent { background: var(--accent-dim); color: var(--accent); }
    .msg-avatar.user  { background: #1e2a20; color: #4ade80; }

    .msg-body { display: flex; flex-direction: column; gap: 6px; min-width: 0; }

    .msg-bubble {
      padding: 12px 16px;
      border-radius: 12px;
      font-size: 14px;
      line-height: 1.7;
      word-break: break-word;
    }
    .msg-bubble.agent {
      background: var(--agent-bg);
      border: 1px solid var(--border);
      border-top-left-radius: 4px;
      color: var(--text);
    }
    .msg-bubble.user {
      background: var(--user-bg);
      border: 1px solid var(--accent-dim);
      border-top-right-radius: 4px;
      color: var(--text);
    }
    .msg-bubble.loading {
      color: var(--text-dim);
      font-style: italic;
    }
    .msg-bubble.loading::after {
      content: '';
      display: inline-block;
      width: 6px; height: 6px;
      border-radius: 50%;
      background: var(--accent);
      margin-left: 8px;
      animation: pulse 1s infinite;
      vertical-align: middle;
    }
    @keyframes pulse {
      0%, 100% { opacity: .3; transform: scale(.8); }
      50%       { opacity: 1;  transform: scale(1); }
    }

    .msg-fuentes {
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
      margin-top: 4px;
    }
    .fuente-tag {
      font-family: 'DM Mono', monospace;
      font-size: 10px;
      background: var(--tag-bg);
      border: 1px solid var(--tag-border);
      color: var(--text-dim);
      padding: 2px 8px;
      border-radius: 4px;
    }

    /* ── Input ── */
    .input-area {
      padding: 20px 28px;
      border-top: 1px solid var(--border);
      flex-shrink: 0;
    }
    .input-row {
      display: flex;
      gap: 10px;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 6px 6px 6px 16px;
      transition: border-color .15s;
    }
    .input-row:focus-within { border-color: var(--accent); }

    .input-field {
      flex: 1;
      background: transparent;
      border: none;
      outline: none;
      font-family: 'DM Sans', sans-serif;
      font-size: 14px;
      color: var(--text);
      padding: 8px 0;
    }
    .input-field::placeholder { color: var(--text-muted); }
    .input-field:disabled     { cursor: not-allowed; }

    .send-btn {
      padding: 8px 18px;
      background: var(--accent);
      color: #fff;
      border: none;
      border-radius: 8px;
      font-family: 'DM Sans', sans-serif;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      transition: background .15s, transform .1s;
      flex-shrink: 0;
    }
    .send-btn:hover:not(:disabled)  { background: #3d68e8; }
    .send-btn:active:not(:disabled) { transform: scale(.97); }
    .send-btn:disabled { background: var(--border); color: var(--text-muted); cursor: not-allowed; }

    .input-hint {
      font-size: 11px;
      color: var(--text-muted);
      text-align: center;
      margin-top: 10px;
    }
  </style>
</head>
<body>
<div class="shell">

  <!-- Sidebar -->
  <aside class="sidebar">
    <div class="logo">
      <div class="logo-icon">🤖</div>
      <div>
        <div class="logo-text">PM Agent</div>
        <div class="logo-sub">Consultas de reuniones</div>
      </div>
    </div>

    <div class="sidebar-section">
      <div class="sidebar-label">Proyecto</div>
      <select class="proyecto-select" id="proyectoSelect">
        <option value="">Cargando...</option>
      </select>
    </div>

    <button class="new-chat-btn" id="newChatBtn">
      <span>＋</span> Nueva consulta
    </button>

    <div class="tips">
      <div class="tips-title">EJEMPLOS DE PREGUNTAS</div>
      <div class="tips-item">¿Qué se decidió sobre <em>la estrategia de rollback</em>?</div>
      <div class="tips-item">¿Qué explicó Juan en la <em>reunión semanal de la semana pasada</em>?</div>
      <div class="tips-item">¿Cuáles son las <em>dependencias</em> identificadas en las últimas reuniones?</div>
      <div class="tips-item">¿Quién se comprometió a <em>revisar el cronograma</em>?</div>
    </div>
  </aside>

  <!-- Chat -->
  <div class="chat-area">
    <div class="chat-header">
      <div class="status-dot" id="statusDot"></div>
      <div>
        <div class="chat-header-title" id="headerTitle">PM Agent</div>
        <div class="chat-header-sub" id="headerSub">Seleccioná un proyecto para empezar</div>
      </div>
    </div>

    <div class="messages" id="messages">
      <div class="empty-state" id="emptyState">
        <div class="empty-icon">💬</div>
        <div class="empty-title">¿Sobre qué reunión querés saber?</div>
        <div class="empty-sub">
          Seleccioná un proyecto en el panel izquierdo<br>
          y hacé tu pregunta en lenguaje natural.
        </div>
      </div>
    </div>

    <div class="input-area">
      <div class="input-row">
        <input
          type="text"
          class="input-field"
          id="inputField"
          placeholder="Seleccioná un proyecto para empezar..."
          disabled
          autocomplete="off"
        >
        <button class="send-btn" id="sendBtn" disabled>Enviar</button>
      </div>
      <div class="input-hint">Enter para enviar · los resultados citan la fuente</div>
    </div>
  </div>

</div>

<script>
  const selectEl   = document.getElementById('proyectoSelect');
  const messagesEl = document.getElementById('messages');
  const inputEl    = document.getElementById('inputField');
  const sendBtn    = document.getElementById('sendBtn');
  const newChatBtn = document.getElementById('newChatBtn');
  const emptyState = document.getElementById('emptyState');
  const headerTitle= document.getElementById('headerTitle');
  const headerSub  = document.getElementById('headerSub');

  let historial = [];
  let esperando = false;

  // ── Cargar proyectos ──────────────────────────────────────────────────────
  fetch('/proyectos')
    .then(r => r.json())
    .then(proyectos => {
      selectEl.innerHTML = '<option value="">— Seleccioná un proyecto —</option>';
      proyectos.forEach(p => {
        const opt = document.createElement('option');
        opt.value = opt.textContent = p;
        selectEl.appendChild(opt);
      });
    })
    .catch(() => {
      selectEl.innerHTML = '<option value="">Error cargando proyectos</option>';
    });

  // ── Cambio de proyecto ────────────────────────────────────────────────────
  selectEl.addEventListener('change', () => {
    const proyecto = selectEl.value;
    resetChat();
    if (proyecto) {
      inputEl.disabled = false;
      sendBtn.disabled = false;
      inputEl.placeholder = '¿Qué querés saber sobre ' + proyecto + '?';
      headerTitle.textContent = proyecto;
      headerSub.textContent   = 'Transcripts y minutas disponibles';
      inputEl.focus();
    } else {
      inputEl.disabled = true;
      sendBtn.disabled = true;
      inputEl.placeholder = 'Seleccioná un proyecto para empezar...';
      headerTitle.textContent = 'PM Agent';
      headerSub.textContent   = 'Seleccioná un proyecto para empezar';
    }
  });

  // ── Nueva consulta ────────────────────────────────────────────────────────
  newChatBtn.addEventListener('click', () => {
    resetChat();
    if (selectEl.value) inputEl.focus();
  });

  function resetChat() {
    historial = [];
    messagesEl.innerHTML = '';
    messagesEl.appendChild(emptyState);
  }

  // ── Agregar mensaje ───────────────────────────────────────────────────────
  function agregarMensaje(rol, texto, fuentes, esLoading) {
    if (emptyState.parentNode) emptyState.remove();

    const row = document.createElement('div');
    row.className = `msg-row ${rol}`;

    const avatar = document.createElement('div');
    avatar.className = `msg-avatar ${rol === 'user' ? 'user' : 'agent'}`;
    avatar.textContent = rol === 'user' ? '👤' : '🤖';

    const body   = document.createElement('div');
    body.className = 'msg-body';

    const bubble = document.createElement('div');
    bubble.className = `msg-bubble ${rol === 'user' ? 'user' : 'agent'}${esLoading ? ' loading' : ''}`;
    bubble.textContent = texto;
    body.appendChild(bubble);

    if (fuentes && fuentes.length > 0) {
      const fuentesDiv = document.createElement('div');
      fuentesDiv.className = 'msg-fuentes';
      fuentes.forEach(f => {
        const tag = document.createElement('span');
        tag.className   = 'fuente-tag';
        tag.textContent = '📎 ' + f;
        fuentesDiv.appendChild(tag);
      });
      body.appendChild(fuentesDiv);
    }

    row.appendChild(avatar);
    row.appendChild(body);
    messagesEl.appendChild(row);
    messagesEl.scrollTop = messagesEl.scrollHeight;

    return { row, bubble };
  }

  // ── Enviar consulta ───────────────────────────────────────────────────────
  async function enviar() {
    const pregunta = inputEl.value.trim();
    const proyecto = selectEl.value;
    if (!pregunta || !proyecto || esperando) return;

    esperando        = true;
    inputEl.value    = '';
    sendBtn.disabled = true;
    inputEl.disabled = true;

    agregarMensaje('user', pregunta);

    const { row: loadingRow, bubble: loadingBubble } =
      agregarMensaje('agent', 'Buscando en las reuniones...', null, true);

    try {
      const resp = await fetch('/chat', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ pregunta, proyecto, historial }),
      });

      const data = await resp.json();

      if (data.error) {
        loadingBubble.textContent = 'Error: ' + data.error;
        loadingBubble.classList.remove('loading');
      } else {
        loadingRow.remove();
        agregarMensaje('agent', data.respuesta, data.archivos_usados);

        // Solo guardar Q&A en el historial (no el contexto — eso se re-fetcha cada vez)
        historial.push({ role: 'user',      content: pregunta       });
        historial.push({ role: 'assistant', content: data.respuesta });

        // Limitar historial a últimos 6 turnos para no inflar tokens
        if (historial.length > 12) historial = historial.slice(-12);
      }

    } catch (e) {
      loadingBubble.textContent = 'No se pudo conectar con el agente local.';
      loadingBubble.classList.remove('loading');
    }

    esperando        = false;
    sendBtn.disabled = false;
    inputEl.disabled = false;
    inputEl.focus();
  }

  sendBtn.addEventListener('click', enviar);
  inputEl.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) enviar(); });
</script>
</body>
</html>"""


# ─── HTTP HANDLER ───────────────────────────────────────────────────────────
class ChatHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path in ("/", "/chat-ui"):
            body = CHAT_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        elif self.path == "/proyectos":
            data = json.dumps(_proyectos_unicos(), ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self._cors_headers()
            self.end_headers()
            self.wfile.write(data)

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length))
        except Exception:
            self._json(400, {"error": "JSON inválido"})
            return

        if self.path == "/chat":
            pregunta  = body.get("pregunta", "").strip()
            proyecto  = body.get("proyecto", "").strip()
            historial = body.get("historial", [])

            if not pregunta or not proyecto:
                self._json(400, {"error": "Faltan pregunta o proyecto"})
                return

            try:
                resultado = procesar_consulta(pregunta, proyecto, historial)
                self._json(200, resultado)
            except Exception as e:
                log.error(f"[Chat] Error procesando consulta: {e}")
                self._json(500, {"error": str(e)})

        elif self.path == "/crear-tareas":
            try:
                from planner_client import crear_tareas_en_planner
                resultado = crear_tareas_en_planner(
                    body.get("acciones", []),
                    body.get("proyecto", ""),
                )
                self._json(200, {"ok": True, "mensaje": resultado})
            except Exception as e:
                self._json(500, {"ok": False, "mensaje": str(e)})

        elif self.path == "/reprocesar":
            nombre_archivo = body.get("nombre_archivo", "").strip()
            tipo_forzado   = body.get("tipo_forzado", "").strip()

            if not nombre_archivo or not tipo_forzado:
                self._json(400, {"ok": False, "mensaje": "Faltan nombre_archivo o tipo_forzado"})
                return

            try:
                import subprocess
                from pathlib import Path
                from transcriber import transcribir_audio
                from ai_processor import generar_notas
                from output_generator import guardar_html

                recordings    = os.getenv("ONEDRIVE_RECORDINGS_PATH", "")
                output_folder = os.getenv("OUTPUT_FOLDER", "")
                ruta_vtt      = Path(recordings) / nombre_archivo

                if not ruta_vtt.exists():
                    self._json(404, {"ok": False, "mensaje": f"No se encontro: {nombre_archivo}"})
                    return

                log.info(f"[Reprocesar] {nombre_archivo} -> tipo forzado: {tipo_forzado}")
                transcript = transcribir_audio(str(ruta_vtt))
                notas      = generar_notas(transcript, nombre_archivo, tipo_forzado=tipo_forzado)
                ruta_html  = guardar_html(notas, nombre_archivo, output_folder)

                try:
                    subprocess.Popen(["cmd", "/c", "start", "", str(ruta_html)], shell=False)
                except Exception:
                    pass

                self._json(200, {"ok": True, "mensaje": f"Nueva minuta generada: {Path(ruta_html).name}"})

            except Exception as e:
                log.error(f"[Reprocesar] Error: {e}")
                self._json(500, {"ok": False, "mensaje": str(e)})

        elif self.path == "/enviar-mail":
            notas          = body.get("notas") or {}
            nombre_archivo = body.get("nombre_archivo", "").strip()
            ruta_html      = body.get("ruta_html", "").strip()

            if not notas or not ruta_html:
                self._json(400, {"ok": False, "mensaje": "Faltan notas o ruta_html"})
                return

            try:
                from output_generator import regenerar_html, generar_html_email

                # 1) Reescribe el .html guardado con las ediciones — queda como
                #    fuente única de verdad, igual a lo que se manda por mail.
                regenerar_html(notas, nombre_archivo or Path(ruta_html).name, ruta_html)

                # 2) Arma el HTML "email-safe" y abre el borrador en Outlook
                #    (Display, no Send — el envío final lo hace el usuario).
                email_html = generar_html_email(notas)
                asunto     = f"{notas.get('titulo', 'Minuta')} — {notas.get('proyecto', '')}".strip(" —")

                import win32com.client
                outlook = win32com.client.Dispatch("Outlook.Application")
                mail = outlook.CreateItem(0)  # olMailItem
                mail.Subject  = asunto
                mail.HTMLBody = email_html
                mail.Display()

                self._json(200, {"ok": True, "mensaje": "Borrador abierto en Outlook"})

            except Exception as e:
                log.error(f"[EnviarMail] Error: {e}")
                self._json(500, {"ok": False, "mensaje": str(e)})

        else:
            self.send_response(404)
            self.end_headers()
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # silenciar logs HTTP en consola


# ─── ENTRY POINT ────────────────────────────────────────────────────────────
def iniciar_server(puerto: int = 8765):
    server = HTTPServer(("localhost", puerto), ChatHandler)
    log.info(f"[Chat] Agente disponible en http://localhost:{puerto}")
    server.serve_forever()

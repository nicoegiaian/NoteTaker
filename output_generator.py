"""
output_generator.py — Genera el archivo HTML de notas
Soporta el nuevo schema con secciones dinámicas por tipo de reunión,
y mantiene compatibilidad con el schema anterior (gemini_processor, etc.).
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime

log = logging.getLogger(__name__)

TIPO_LABELS = {
    "operativa":     "Operativa",
    "decision":      "Decisión",
    "transferencia": "Transferencia",
    "debate":        "Debate / Análisis",
    "kickoff":       "Kickoff",
    "general":       "General",
}


def guardar_html(notas: dict, nombre_archivo: str, output_folder: str) -> str:
    """
    Genera un archivo HTML con las notas formateadas.
    Detecta automáticamente si usar el schema nuevo (con secciones) o el anterior.
    """
    fecha_hora = datetime.now().strftime("%Y%m%d_%H%M")

    nombre_output = f"{fecha_hora}_{Path(nombre_archivo).stem[:50]}.html"
    nombre_output = "".join(c if c.isalnum() or c in "._- " else "_" for c in nombre_output)
    ruta_output   = os.path.join(output_folder, nombre_output)

    return regenerar_html(notas, nombre_archivo, ruta_output)


def regenerar_html(notas: dict, nombre_archivo: str, ruta_output: str) -> str:
    """
    (Re)escribe un HTML en una ruta puntual — usado tanto por guardar_html (archivo nuevo)
    como por el endpoint de edición/envío por mail (sobrescribe el mismo archivo).
    """
    fecha_hoy = datetime.now().strftime("%d/%m/%Y")
    es_schema_nuevo = "tipo_reunion" in notas and "secciones" in notas

    if es_schema_nuevo:
        html = _generar_html_nuevo(notas, nombre_archivo, fecha_hoy, ruta_output)
    else:
        html = _generar_html_legacy(notas, nombre_archivo, fecha_hoy)

    with open(ruta_output, "w", encoding="utf-8") as f:
        f.write(html)

    return ruta_output


# ─── SCHEMA NUEVO ────────────────────────────────────────────────────────────

def _generar_html_nuevo(notas: dict, nombre_archivo: str, fecha_hoy: str, ruta_output: str = "") -> str:
    tipo         = notas.get("tipo_reunion", "general")
    tipo_label   = TIPO_LABELS.get(tipo, tipo.capitalize())
    html_participantes = _render_chips_editable(notas.get("participantes", []))
    html_acciones      = _render_acciones(notas.get("acciones", []))
    html_secciones     = _render_secciones(notas.get("secciones", []))
    ruta_output_attr   = ruta_output.replace('"', "&quot;")

    tiene_participantes = bool(notas.get("participantes"))
    tiene_acciones      = bool(notas.get("acciones"))

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{notas.get('titulo', nombre_archivo)}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: #f5f5f0; color: #1a1a1a; line-height: 1.6; padding: 40px 20px;
  }}
  .card {{
    background: #ffffff; border-radius: 12px; padding: 40px 48px;
    max-width: 860px; margin: 0 auto; box-shadow: 0 2px 12px rgba(0,0,0,0.06);
  }}
  .header {{ border-bottom: 2px solid #f0f0f0; padding-bottom: 24px; margin-bottom: 32px; }}
  .badges {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }}
  .badge {{
    display: inline-block; font-size: 12px; font-weight: 600;
    letter-spacing: 0.5px; text-transform: uppercase;
    padding: 4px 12px; border-radius: 20px;
  }}
  .badge-proyecto {{ background: #e8f0fe; color: #1a56db; }}
  .badge-tipo     {{ background: #f0fdf4; color: #16a34a; }}
  h1 {{ font-size: 24px; font-weight: 700; color: #111; margin-bottom: 8px; line-height: 1.3; }}
  .meta {{ font-size: 13px; color: #888; display: flex; gap: 16px; flex-wrap: wrap; }}
  h2 {{
    font-size: 13px; font-weight: 700; letter-spacing: 0.8px;
    text-transform: uppercase; color: #888; margin-bottom: 14px;
    display: flex; align-items: center; gap: 8px;
  }}
  .section {{ margin-bottom: 36px; }}
  .resumen {{
    font-size: 15px; color: #333; line-height: 1.75;
    background: #fafafa; border-left: 3px solid #1a56db;
    padding: 16px 20px; border-radius: 0 8px 8px 0;
  }}

  /* Sección tipo destacado */
  .sec-destacado {{
    font-size: 15px; color: #111; line-height: 1.75;
    background: #fffbeb; border-left: 4px solid #f59e0b;
    padding: 16px 20px; border-radius: 0 8px 8px 0; font-weight: 500;
  }}

  /* Sección tipo texto */
  .sec-texto {{ font-size: 14px; color: #333; line-height: 1.75; }}

  /* Sección tipo lista */
  .sec-lista {{ list-style: none; }}
  .sec-lista li {{
    display: flex; align-items: flex-start; gap: 10px;
    padding: 8px 0; font-size: 14px; color: #333;
    border-bottom: 1px solid #f5f5f5;
  }}
  .sec-lista li:last-child {{ border-bottom: none; }}
  .sec-lista li::before {{ content: "•"; color: #1a56db; font-weight: 700; flex-shrink: 0; }}

  /* Sección tipo lista numerada */
  .sec-lista-num {{ list-style: none; counter-reset: items; }}
  .sec-lista-num li {{
    counter-increment: items; display: flex; align-items: flex-start;
    gap: 12px; padding: 10px 0; border-bottom: 1px solid #f5f5f5; font-size: 14px;
  }}
  .sec-lista-num li:last-child {{ border-bottom: none; }}
  .sec-lista-num li::before {{
    content: counter(items); display: flex; align-items: center; justify-content: center;
    width: 24px; height: 24px; background: #1a56db; color: white;
    border-radius: 50%; font-size: 12px; font-weight: 700; flex-shrink: 0;
  }}

  /* Tabla de acciones */
  .acciones-table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  .acciones-table th {{
    background: #f8f8f8; text-align: left; padding: 10px 14px;
    font-size: 12px; font-weight: 600; color: #666;
    text-transform: uppercase; letter-spacing: 0.4px; border-bottom: 2px solid #eee;
  }}
  .acciones-table th:nth-child(1), .acciones-table td:nth-child(1) {{ width: 55%; }}
  .acciones-table th:nth-child(2), .acciones-table td:nth-child(2) {{ width: 28%; }}
  .acciones-table th:nth-child(3), .acciones-table td:nth-child(3) {{ width: 17%; }}
  .acciones-table td {{
    padding: 12px 14px; border-bottom: 1px solid #f0f0f0;
    vertical-align: top; word-wrap: break-word; overflow-wrap: break-word;
  }}
  .acciones-table tr:last-child td {{ border-bottom: none; }}
  .acciones-table tr:hover td {{ background: #fafafa; }}
  .responsables-cell {{ display: flex; flex-wrap: wrap; gap: 4px; }}
  .responsable-chip {{
    display: inline-block; background: #f0fdf4; color: #16a34a;
    border: 1px solid #bbf7d0; font-size: 12px; font-weight: 500;
    padding: 2px 10px; border-radius: 20px;
  }}
  .fecha-chip {{
    display: inline-block; background: #fff7ed; color: #c2410c;
    border: 1px solid #fed7aa; font-size: 12px; font-weight: 500;
    padding: 2px 10px; border-radius: 20px;
  }}
  .fecha-chip.sin-fecha {{ background: #f8f8f8; color: #999; border-color: #e5e5e5; }}

  /* Participantes chips */
  .chips-container {{ display: flex; flex-wrap: wrap; gap: 8px; }}
  .chip {{
    background: #f3f4f6; color: #374151; border: 1px solid #e5e7eb;
    font-size: 13px; font-weight: 500; padding: 4px 12px; border-radius: 20px;
  }}
  .copy-chips-btn {{
    font-size: 11px; font-weight: 600; padding: 2px 10px;
    background: #e8f0fe; color: #1a56db; border: 1px solid #c7d7fc;
    border-radius: 20px; cursor: pointer; transition: background 0.2s;
    text-transform: none; letter-spacing: 0; vertical-align: middle;
  }}
  .copy-chips-btn:hover {{ background: #c7d7fc; }}

  /* Botón copiar */
  .copy-btn {{
    display: block; width: 100%; padding: 14px; background: #1a56db;
    color: white; border: none; border-radius: 8px; font-size: 14px;
    font-weight: 600; cursor: pointer; margin-top: 32px; transition: background 0.2s;
  }}
  .copy-btn:hover {{ background: #1e429f; }}
  .copy-btn.copied {{ background: #16a34a; }}

  /* Reprocesar */
  .reprocesar-section {{
    margin-top: 16px; padding: 16px; background: #f8f9fa;
    border: 1px solid #e5e7eb; border-radius: 8px;
    display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
  }}
  .reprocesar-label {{ font-size: 13px; color: #6b7280; flex-shrink: 0; }}
  .tipo-select {{
    flex: 1; min-width: 200px; padding: 8px 12px; border: 1px solid #d1d5db;
    border-radius: 6px; font-size: 13px; color: #374151;
    background: white; cursor: pointer;
  }}
  .reprocesar-btn {{
    padding: 8px 16px; background: #6b7280; color: white; border: none;
    border-radius: 6px; font-size: 13px; font-weight: 600;
    cursor: pointer; transition: background 0.2s; white-space: nowrap;
  }}
  .reprocesar-btn:hover:not(:disabled) {{ background: #4b5563; }}
  .reprocesar-btn:disabled {{ cursor: not-allowed; opacity: 0.7; }}

  .footer {{ text-align: center; font-size: 12px; color: #bbb; margin-top: 20px; }}
  @media print {{
    body {{ background: white; padding: 0; }}
    .card {{ box-shadow: none; padding: 20px; }}
    .copy-btn, .reprocesar-section, .acciones-fila {{ display: none; }}
  }}

  /* Edición y envío por mail */
  .acciones-fila {{ display: flex; gap: 10px; margin-top: 32px; }}
  .acciones-fila .copy-btn {{ margin-top: 0; flex: 2; }}
  .edit-btn, .mail-btn {{
    flex: 1; padding: 14px; border: none; border-radius: 8px; white-space: nowrap;
    font-size: 14px; font-weight: 600; cursor: pointer; transition: background 0.2s;
  }}
  .edit-btn {{ background: #6b7280; color: white; }}
  .edit-btn:hover {{ background: #4b5563; }}
  .edit-btn.activo {{ background: #16a34a; }}
  .mail-btn {{ background: #ea580c; color: white; }}
  .mail-btn:hover:not(:disabled) {{ background: #c2410c; }}
  .mail-btn:disabled {{ opacity: .6; cursor: not-allowed; }}

  .del-sec-btn, .del-row-btn, .del-item-btn, .del-chip-btn {{
    display: none; border: none; background: #fee2e2; color: #dc2626;
    border-radius: 4px; font-size: 11px; cursor: pointer; margin-left: 8px;
    padding: 1px 6px; vertical-align: middle;
  }}
  body.modo-edicion .del-sec-btn,
  body.modo-edicion .del-row-btn,
  body.modo-edicion .del-item-btn,
  body.modo-edicion .del-chip-btn {{ display: inline-block; }}

  .acciones-table td.del-col {{ width: 28px; padding: 4px; text-align: center; }}

  body.modo-edicion [contenteditable="true"] {{
    outline: 1px dashed #93c5fd; outline-offset: 2px; border-radius: 4px;
    background: #f8faff;
  }}
  body.modo-edicion [contenteditable="true"]:focus {{ outline: 2px solid #1a56db; }}
</style>
</head>
<body>
<div class="card" data-tipo-reunion="{tipo}" data-ruta-html="{ruta_output_attr}">

  <div class="header">
    <div class="badges">
      <span class="badge badge-proyecto">{notas.get('proyecto', 'Sin proyecto')}</span>
      <span class="badge badge-tipo">📋 {tipo_label}</span>
    </div>
    <h1>{notas.get('titulo', nombre_archivo)}</h1>
    <div class="meta">
      <span>📅 {fecha_hoy}</span>
      <span>📂 {nombre_archivo}</span>
    </div>
  </div>

  <div class="section">
    <h2>📋 Resumen</h2>
    <p class="resumen">{notas.get('resumen', 'Sin resumen disponible.')}</p>
  </div>

  {"" if not tiene_participantes else f'''
  <div class="section">
    <h2>👥 Participantes <button class="copy-chips-btn" onclick="copiarParticipantes(this)">📧 Copiar</button></h2>
    <div class="chips-container">{html_participantes}</div>
  </div>
  '''}

  {html_secciones}

  {"" if not tiene_acciones else f'''
  <div class="section">
    <h2>✅ Acciones</h2>
    {html_acciones}
  </div>
  '''}

  <div class="acciones-fila">
    <button class="copy-btn" onclick="copiarContenido(this)">
      📋 Copiar todo para pegar en Loop
    </button>
    <button class="edit-btn" id="editBtn" onclick="toggleEdicion()" type="button">✏️ Editar</button>
    <button class="mail-btn" id="mailBtn" onclick="enviarPorMail(this)" type="button">📧 Enviar por mail</button>
  </div>

  <div class="reprocesar-section">
    <span class="reprocesar-label">¿El tipo de reunión no es correcto?</span>
    <select class="tipo-select" id="tipoSelect">
      <option value="">— Seleccioná el tipo correcto —</option>
      <option value="operativa">Operativa / Avance</option>
      <option value="decision">Decisión</option>
      <option value="transferencia">Transferencia de conocimiento</option>
      <option value="debate">Debate / Análisis</option>
      <option value="kickoff">Kickoff</option>
      <option value="general">General</option>
    </select>
    <button class="reprocesar-btn" onclick="reprocesar(this)" data-archivo="{nombre_archivo}">
      🔄 Reprocesar
    </button>
  </div>

</div>

<div class="footer">
  Generado automáticamente · Meeting Notes Bot · {fecha_hoy}
</div>

<script>
function copiarContenido(btn) {{
  const card = document.querySelector('.card');
  const extras = card.querySelectorAll('.copy-btn, .reprocesar-section');
  extras.forEach(e => e.style.display = 'none');
  const range = document.createRange();
  range.selectNode(card);
  window.getSelection().removeAllRanges();
  window.getSelection().addRange(range);
  document.execCommand('copy');
  window.getSelection().removeAllRanges();
  extras.forEach(e => e.style.display = '');
  btn.textContent = '✅ Copiado — ahora pegalo en Loop (Ctrl+V)';
  btn.classList.add('copied');
  setTimeout(() => {{
    btn.textContent = '📋 Copiar todo para pegar en Loop';
    btn.classList.remove('copied');
  }}, 4000);
}}

function copiarParticipantes(btn) {{
  const chips = btn.closest('.section').querySelectorAll('.chip');
  const texto = Array.from(chips).map(c => c.textContent.trim()).join('; ');
  navigator.clipboard.writeText(texto).then(() => {{
    const orig = btn.textContent;
    btn.textContent = '✅ Copiado';
    setTimeout(() => {{ btn.textContent = orig; }}, 2000);
  }});
}}

// ── Edición antes de enviar ─────────────────────────────────────────────────
function toggleEdicion() {{
  const activo = document.body.classList.toggle('modo-edicion');
  const editables = document.querySelectorAll(
    '.card > .header h1, .card .resumen, .card .sec-destacado, .card .sec-texto, ' +
    '.card .sec-lista li > span, .card .sec-lista-num li > span, ' +
    '.card .acciones-table td:nth-child(1), ' +
    '.card .responsables-cell, .card .fecha-chip'
  );
  editables.forEach(el => el.setAttribute('contenteditable', activo ? 'true' : 'false'));
  const btn = document.getElementById('editBtn');
  btn.textContent = activo ? '✅ Listo' : '✏️ Editar';
  btn.classList.toggle('activo', activo);
}}

function eliminarSeccion(btn) {{ btn.closest('.section').remove(); }}
function eliminarRow(btn)     {{ btn.closest('tr').remove(); }}
function eliminarItem(btn)    {{ btn.closest('li').remove(); }}
function eliminarChip(btn)    {{ btn.closest('.chip').remove(); }}

// ── Extrae el estado actual (editado) a la misma forma que usa el generador ──
function extraerNotas() {{
  const card  = document.querySelector('.card');
  const notas = {{ tipo_reunion: card.getAttribute('data-tipo-reunion') || 'general', secciones: [] }};

  const h1 = card.querySelector('.header h1');
  notas.titulo = h1 ? h1.textContent.trim() : '';

  const badgeProyecto = card.querySelector('.badge-proyecto');
  notas.proyecto = badgeProyecto ? badgeProyecto.textContent.trim() : '';

  const resumenEl = card.querySelector('.resumen');
  notas.resumen = resumenEl ? resumenEl.textContent.trim() : '';

  const chipsContainer = card.querySelector('.chips-container');
  notas.participantes = chipsContainer
    ? Array.from(chipsContainer.querySelectorAll('.chip'))
        .map(c => (c.childNodes[0] ? c.childNodes[0].textContent : c.textContent).trim())
        .filter(Boolean)
    : [];

  card.querySelectorAll('.section[data-tipo]').forEach(sec => {{
    const tipo = sec.getAttribute('data-tipo');
    const h2   = sec.querySelector('h2');
    const titulo = h2 ? h2.textContent.replace('🗑', '').trim() : '';
    let contenido;
    if (tipo === 'destacado') {{
      const el = sec.querySelector('.sec-destacado');
      contenido = el ? el.textContent.trim() : '';
    }} else if (tipo === 'texto') {{
      const el = sec.querySelector('.sec-texto');
      contenido = el ? el.textContent.trim() : '';
    }} else {{
      contenido = Array.from(sec.querySelectorAll('li > span'))
        .map(s => s.textContent.trim()).filter(Boolean);
    }}
    notas.secciones.push({{ tipo, titulo, contenido }});
  }});

  notas.acciones = [];
  card.querySelectorAll('.acciones-table tbody tr').forEach(tr => {{
    const tds = tr.querySelectorAll('td');
    if (tds.length < 3) return;
    const descripcion = tds[0].textContent.trim();
    if (!descripcion) return;
    notas.acciones.push({{
      descripcion,
      responsable:  tds[1].textContent.trim() || 'Por definir',
      fecha_limite: tds[2].textContent.trim() || 'Sin fecha definida',
    }});
  }});

  return notas;
}}

// ── Enviar por mail (abre borrador en Outlook con formato "email-safe") ──────
async function enviarPorMail(btn) {{
  const notas          = extraerNotas();
  const reprocesarBtn  = document.querySelector('[data-archivo]');
  const nombreArchivo  = reprocesarBtn ? reprocesarBtn.getAttribute('data-archivo') : '';
  const rutaHtml       = document.querySelector('.card').getAttribute('data-ruta-html');

  const textoOriginal = btn.textContent;
  btn.textContent = '⏳ Abriendo Outlook...';
  btn.disabled = true;
  try {{
    const resp = await fetch('http://localhost:8765/enviar-mail', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ notas, nombre_archivo: nombreArchivo, ruta_html: rutaHtml }}),
    }});
    const data = await resp.json();
    btn.textContent = data.ok ? '✅ ' + data.mensaje : '❌ ' + data.mensaje;
  }} catch (e) {{
    btn.textContent = '❌ No se pudo conectar al bot local';
  }}
  setTimeout(() => {{ btn.textContent = textoOriginal; btn.disabled = false; }}, 4000);
}}

async function reprocesar(btn) {{
  const select = document.getElementById('tipoSelect');
  const tipo = select.value;
  if (!tipo) {{ alert('Seleccioná un tipo de reunión primero.'); return; }}
  const nombreArchivo = btn.getAttribute('data-archivo');
  btn.textContent = '⏳ Reprocesando...';
  btn.disabled = true;
  try {{
    const resp = await fetch('http://localhost:8765/reprocesar', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ nombre_archivo: nombreArchivo, tipo_forzado: tipo }})
    }});
    const data = await resp.json();
    if (data.ok) {{
      btn.textContent = '✅ ' + data.mensaje;
    }} else {{
      btn.textContent = '❌ ' + data.mensaje;
      btn.disabled = false;
    }}
  }} catch(e) {{
    btn.textContent = '❌ No se pudo conectar al bot local';
    btn.disabled = false;
  }}
}}
</script>
</body>
</html>"""


# ─── RENDERERS DE SECCIONES DINÁMICAS ────────────────────────────────────────

def _render_secciones(secciones: list) -> str:
    if not secciones:
        return ""
    partes = []
    for sec in secciones:
        tipo     = sec.get("tipo", "lista")
        titulo   = sec.get("titulo", "")
        contenido = sec.get("contenido", "")

        del_item = '<button class="del-item-btn" onclick="eliminarItem(this)" type="button">×</button>'

        if tipo == "destacado":
            body = f'<div class="sec-destacado">{contenido}</div>'
        elif tipo == "texto":
            body = f'<p class="sec-texto">{contenido}</p>'
        elif tipo == "lista":
            items = contenido if isinstance(contenido, list) else [contenido]
            lis = "".join(f"<li><span>{item}</span>{del_item}</li>" for item in items if item)
            body = f'<ul class="sec-lista">{lis}</ul>'
        elif tipo == "lista_numerada":
            items = contenido if isinstance(contenido, list) else [contenido]
            lis = "".join(f"<li><span>{item}</span>{del_item}</li>" for item in items if item)
            body = f'<ol class="sec-lista-num">{lis}</ol>'
        else:
            body = f'<p class="sec-texto">{contenido}</p>'

        partes.append(f'''
  <div class="section" data-tipo="{tipo}">
    <h2>{titulo} <button class="del-sec-btn" onclick="eliminarSeccion(this)" type="button">🗑</button></h2>
    {body}
  </div>''')

    return "\n".join(partes)


# ─── SCHEMA LEGACY (compatibilidad con gemini_processor y otros) ─────────────

def _generar_html_legacy(notas: dict, nombre_archivo: str, fecha_hoy: str) -> str:
    """Genera HTML con el schema anterior para mantener compatibilidad."""
    html_acciones      = _render_acciones(notas.get("acciones", []))
    html_dependencias  = _render_dependencias(notas.get("dependencias", []))
    html_proximos      = _render_lista_legacy(notas.get("proximos_pasos", []))
    html_participantes = _render_chips(notas.get("participantes", []))
    html_pendientes    = _render_lista_legacy(notas.get("temas_pendientes", []))
    tiene_pendientes   = bool(notas.get("temas_pendientes"))

    # Reutiliza el mismo CSS del schema nuevo más el legacy específico
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{notas.get('titulo', nombre_archivo)}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Inter', sans-serif; background: #f5f5f0; color: #1a1a1a; line-height: 1.6; padding: 40px 20px; }}
  .card {{ background: #fff; border-radius: 12px; padding: 40px 48px; max-width: 860px; margin: 0 auto; box-shadow: 0 2px 12px rgba(0,0,0,0.06); }}
  .header {{ border-bottom: 2px solid #f0f0f0; padding-bottom: 24px; margin-bottom: 32px; }}
  .proyecto-badge {{ display: inline-block; background: #e8f0fe; color: #1a56db; font-size: 12px; font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase; padding: 4px 12px; border-radius: 20px; margin-bottom: 12px; }}
  h1 {{ font-size: 24px; font-weight: 700; color: #111; margin-bottom: 8px; line-height: 1.3; }}
  .meta {{ font-size: 13px; color: #888; display: flex; gap: 16px; flex-wrap: wrap; }}
  h2 {{ font-size: 13px; font-weight: 700; letter-spacing: 0.8px; text-transform: uppercase; color: #888; margin-bottom: 14px; display: flex; align-items: center; gap: 8px; }}
  .section {{ margin-bottom: 36px; }}
  .resumen {{ font-size: 15px; color: #333; line-height: 1.75; background: #fafafa; border-left: 3px solid #1a56db; padding: 16px 20px; border-radius: 0 8px 8px 0; }}
  .acciones-table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  .acciones-table th {{ background: #f8f8f8; text-align: left; padding: 10px 14px; font-size: 12px; font-weight: 600; color: #666; text-transform: uppercase; letter-spacing: 0.4px; border-bottom: 2px solid #eee; }}
  .acciones-table th:nth-child(1), .acciones-table td:nth-child(1) {{ width: 55%; }}
  .acciones-table th:nth-child(2), .acciones-table td:nth-child(2) {{ width: 28%; }}
  .acciones-table th:nth-child(3), .acciones-table td:nth-child(3) {{ width: 17%; }}
  .acciones-table td {{ padding: 12px 14px; border-bottom: 1px solid #f0f0f0; vertical-align: top; word-wrap: break-word; }}
  .acciones-table tr:last-child td {{ border-bottom: none; }}
  .responsables-cell {{ display: flex; flex-wrap: wrap; gap: 4px; }}
  .responsable-chip {{ display: inline-block; background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0; font-size: 12px; font-weight: 500; padding: 2px 10px; border-radius: 20px; }}
  .fecha-chip {{ display: inline-block; background: #fff7ed; color: #c2410c; border: 1px solid #fed7aa; font-size: 12px; font-weight: 500; padding: 2px 10px; border-radius: 20px; }}
  .fecha-chip.sin-fecha {{ background: #f8f8f8; color: #999; border-color: #e5e5e5; }}
  .dep-item {{ display: flex; align-items: flex-start; gap: 12px; padding: 12px 16px; background: #fefce8; border: 1px solid #fde68a; border-radius: 8px; margin-bottom: 10px; font-size: 14px; }}
  .pasos-list {{ list-style: none; counter-reset: pasos; }}
  .pasos-list li {{ counter-increment: pasos; display: flex; align-items: flex-start; gap: 12px; padding: 10px 0; border-bottom: 1px solid #f5f5f5; font-size: 14px; }}
  .pasos-list li:last-child {{ border-bottom: none; }}
  .pasos-list li::before {{ content: counter(pasos); display: flex; align-items: center; justify-content: center; width: 24px; height: 24px; background: #1a56db; color: white; border-radius: 50%; font-size: 12px; font-weight: 700; flex-shrink: 0; }}
  .chips-container {{ display: flex; flex-wrap: wrap; gap: 8px; }}
  .chip {{ background: #f3f4f6; color: #374151; border: 1px solid #e5e7eb; font-size: 13px; font-weight: 500; padding: 4px 12px; border-radius: 20px; }}
  .copy-chips-btn {{ font-size: 11px; font-weight: 600; padding: 2px 10px; background: #e8f0fe; color: #1a56db; border: 1px solid #c7d7fc; border-radius: 20px; cursor: pointer; transition: background 0.2s; text-transform: none; letter-spacing: 0; vertical-align: middle; }}
  .copy-chips-btn:hover {{ background: #c7d7fc; }}
  .pendientes-list {{ list-style: none; }}
  .pendientes-list li {{ display: flex; align-items: flex-start; gap: 10px; padding: 8px 0; font-size: 14px; color: #555; border-bottom: 1px solid #f5f5f5; }}
  .pendientes-list li:last-child {{ border-bottom: none; }}
  .pendientes-list li::before {{ content: "⚠️"; flex-shrink: 0; }}
  .copy-btn {{ display: block; width: 100%; padding: 14px; background: #1a56db; color: white; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; margin-top: 32px; transition: background 0.2s; }}
  .copy-btn:hover {{ background: #1e429f; }}
  .copy-btn.copied {{ background: #16a34a; }}
  .footer {{ text-align: center; font-size: 12px; color: #bbb; margin-top: 20px; }}
  @media print {{ body {{ background: white; padding: 0; }} .card {{ box-shadow: none; padding: 20px; }} .copy-btn {{ display: none; }} }}
</style>
</head>
<body>
<div class="card">
  <div class="header">
    <div class="proyecto-badge">{notas.get('proyecto', 'Sin proyecto')}</div>
    <h1>{notas.get('titulo', nombre_archivo)}</h1>
    <div class="meta"><span>📅 {fecha_hoy}</span><span>📂 {nombre_archivo}</span></div>
  </div>
  <div class="section"><h2>📋 Resumen</h2><p class="resumen">{notas.get('resumen', 'Sin resumen disponible.')}</p></div>
  {"" if not notas.get('participantes') else f'<div class="section"><h2>👥 Participantes <button class="copy-chips-btn" onclick="copiarParticipantes(this)">📧 Copiar</button></h2><div class="chips-container">{html_participantes}</div></div>'}
  <div class="section"><h2>✅ Acciones</h2>{html_acciones}</div>
  {"" if not notas.get('dependencias') else f'<div class="section"><h2>🔗 Dependencias</h2>{html_dependencias}</div>'}
  <div class="section"><h2>🚀 Próximos Pasos</h2>{html_proximos}</div>
  {"" if not tiene_pendientes else f'<div class="section"><h2>⚠️ Temas Pendientes</h2><ul class="pendientes-list">{html_pendientes}</ul></div>'}
  <button class="copy-btn" onclick="copiarContenido(this)">📋 Copiar todo para pegar en Loop</button>
</div>
<div class="footer">Generado automáticamente · Meeting Notes Bot · {fecha_hoy}</div>
<script>
function copiarContenido(btn) {{
  const card = document.querySelector('.card');
  const botones = card.querySelectorAll('button');
  botones.forEach(b => b.style.display = 'none');
  const range = document.createRange(); range.selectNode(card);
  window.getSelection().removeAllRanges(); window.getSelection().addRange(range);
  document.execCommand('copy'); window.getSelection().removeAllRanges();
  botones.forEach(b => b.style.display = 'block');
  btn.textContent = '✅ Copiado — ahora pegalo en Loop (Ctrl+V)';
  btn.classList.add('copied');
  setTimeout(() => {{ btn.textContent = '📋 Copiar todo para pegar en Loop'; btn.classList.remove('copied'); }}, 4000);
}}
function copiarParticipantes(btn) {{
  const chips = btn.closest('.section').querySelectorAll('.chip');
  const texto = Array.from(chips).map(c => c.textContent.trim()).join('; ');
  navigator.clipboard.writeText(texto).then(() => {{
    const orig = btn.textContent;
    btn.textContent = '✅ Copiado';
    setTimeout(() => {{ btn.textContent = orig; }}, 2000);
  }});
}}
</script>
</body>
</html>"""


# ─── HELPERS COMPARTIDOS ─────────────────────────────────────────────────────

def _render_responsables(responsable_str: str) -> str:
    if not responsable_str or responsable_str == "Por definir":
        return '<span class="responsable-chip">Por definir</span>'
    import re
    partes = re.split(r',|/| y | & ', responsable_str)
    return "".join(
        f'<span class="responsable-chip">{p.strip()}</span>'
        for p in partes if p.strip()
    )


def _render_acciones(acciones: list) -> str:
    if not acciones:
        return '<p style="color:#888;font-size:14px;">No se identificaron acciones específicas.</p>'
    filas = ""
    for a in acciones:
        tiene_fecha = a.get("fecha_limite", "Sin fecha definida") != "Sin fecha definida"
        clase_fecha = "fecha-chip" if tiene_fecha else "fecha-chip sin-fecha"
        chips = _render_responsables(a.get('responsable', 'Por definir'))
        filas += f"""
        <tr>
          <td>{a.get('descripcion', '')}</td>
          <td><div class="responsables-cell">{chips}</div></td>
          <td><span class="{clase_fecha}">{a.get('fecha_limite', 'Sin fecha')}</span></td>
          <td class="del-col"><button class="del-row-btn" onclick="eliminarRow(this)" type="button">🗑</button></td>
        </tr>"""
    return f"""
    <table class="acciones-table">
      <thead><tr><th>Acción</th><th>Responsable</th><th>Fecha límite</th><th></th></tr></thead>
      <tbody>{filas}</tbody>
    </table>"""


def _render_dependencias(dependencias: list) -> str:
    if not dependencias:
        return ""
    items = ""
    for d in dependencias:
        items += f"""
        <div class="dep-item">
          <span>⛓️</span>
          <div><strong>{d.get('descripcion', '')}</strong><br>
          <span style="color:#78716c;font-size:13px;">Depende de: {d.get('depende_de', 'No especificado')}</span></div>
        </div>"""
    return items


def _render_lista_legacy(items: list) -> str:
    if not items:
        return '<p style="color:#888;font-size:14px;">No hay ítems registrados.</p>'
    lis = "".join(f"<li>{item}</li>" for item in items)
    return f'<ol class="pasos-list">{lis}</ol>'


def _render_chips(items: list) -> str:
    return "".join(f'<span class="chip">{item}</span>' for item in items)


def _render_chips_editable(items: list) -> str:
    """Como _render_chips, pero con un botón para quitar el participante en modo edición."""
    return "".join(
        f'<span class="chip">{item}<button class="del-chip-btn" onclick="eliminarChip(this)" type="button">×</button></span>'
        for item in items
    )


# ─── HTML "EMAIL-SAFE" PARA OUTLOOK ──────────────────────────────────────────

def generar_html_email(notas: dict) -> str:
    """
    Genera el cuerpo del mail (HTMLBody) a partir de las mismas notas, pero con
    tablas + estilos inline en vez de flexbox/gap/box-shadow/fuentes custom —
    lo que sí soporta el motor de Word que usa Outlook para renderizar el cuerpo.
    """
    FUENTE = "'Segoe UI', Arial, sans-serif"
    AZUL   = "#1a56db"
    VERDE  = "#16a34a"
    GRIS   = "#666666"

    tipo       = notas.get("tipo_reunion", "general")
    tipo_label = TIPO_LABELS.get(tipo, tipo.capitalize())
    fecha_hoy  = datetime.now().strftime("%d/%m/%Y")

    def badge(texto: str, bg: str, color: str) -> str:
        return (
            f'<span style="display:inline-block;background:{bg};color:{color};'
            f'font-size:11px;font-weight:600;letter-spacing:.4px;text-transform:uppercase;'
            f'padding:3px 10px;margin-right:6px;font-family:{FUENTE};">{texto}</span>'
        )

    def titulo_seccion(texto: str) -> str:
        return (
            f'<tr><td style="padding:22px 0 8px 0;font-size:12px;font-weight:700;'
            f'letter-spacing:.6px;text-transform:uppercase;color:{GRIS};font-family:{FUENTE};">{texto}</td></tr>'
        )

    filas = [
        f'<tr><td>{badge(notas.get("proyecto", "Sin proyecto"), "#e8f0fe", AZUL)}'
        f'{badge(f"📋 {tipo_label}", "#f0fdf4", VERDE)}</td></tr>',
        f'<tr><td style="padding:10px 0 4px 0;font-size:22px;font-weight:700;color:#111;'
        f'font-family:{FUENTE};">{notas.get("titulo", "")}</td></tr>',
        f'<tr><td style="padding:0 0 18px 0;font-size:12px;color:#888;font-family:{FUENTE};'
        f'border-bottom:2px solid #f0f0f0;">📅 {fecha_hoy}</td></tr>',
        titulo_seccion("📋 Resumen"),
        f'''<tr><td>
          <table cellpadding="0" cellspacing="0" style="width:100%;background:#fafafa;">
            <tr>
              <td width="3" style="background:{AZUL};font-size:1px;line-height:1px;">&nbsp;</td>
              <td style="padding:14px 18px;font-size:14px;line-height:1.7;color:#333;font-family:{FUENTE};">{notas.get('resumen', 'Sin resumen disponible.')}</td>
            </tr>
          </table>
        </td></tr>''',
    ]

    participantes = notas.get("participantes") or []
    if participantes:
        chips = " ".join(
            f'<span style="display:inline-block;background:#f3f4f6;color:#374151;border:1px solid #e5e7eb;'
            f'font-size:12px;padding:3px 10px;margin:0 6px 6px 0;font-family:{FUENTE};">{p}</span>'
            for p in participantes
        )
        filas.append(titulo_seccion("👥 Participantes"))
        filas.append(f'<tr><td style="padding-bottom:4px;">{chips}</td></tr>')

    for sec in notas.get("secciones", []):
        stipo     = sec.get("tipo", "lista")
        stitulo   = sec.get("titulo", "")
        contenido = sec.get("contenido", "")
        filas.append(titulo_seccion(stitulo))

        if stipo == "destacado":
            filas.append(f'''<tr><td>
              <table cellpadding="0" cellspacing="0" style="width:100%;background:#fffbeb;">
                <tr>
                  <td width="4" style="background:#f59e0b;font-size:1px;line-height:1px;">&nbsp;</td>
                  <td style="padding:14px 18px;font-size:14px;font-weight:500;color:#111;font-family:{FUENTE};">{contenido}</td>
                </tr>
              </table>
            </td></tr>''')
        elif stipo == "texto":
            filas.append(
                f'<tr><td style="font-size:14px;color:#333;line-height:1.7;font-family:{FUENTE};">{contenido}</td></tr>'
            )
        else:
            items     = contenido if isinstance(contenido, list) else [contenido]
            numerada  = stipo == "lista_numerada"
            filas_li  = ""
            for i, item in enumerate(items, 1):
                if not item:
                    continue
                marca = f"{i}." if numerada else "•"
                filas_li += (
                    f'<tr><td style="padding:6px 0;border-bottom:1px solid #f5f5f5;font-size:14px;'
                    f'color:#333;font-family:{FUENTE};"><span style="color:{AZUL};font-weight:700;">{marca}</span> {item}</td></tr>'
                )
            filas.append(f'<tr><td><table cellpadding="0" cellspacing="0" style="width:100%;">{filas_li}</table></td></tr>')

    acciones = notas.get("acciones") or []
    if acciones:
        filas.append(titulo_seccion("✅ Acciones"))
        filas_acc = ""
        for a in acciones:
            filas_acc += (
                '<tr>'
                f'<td style="padding:10px 12px;border-bottom:1px solid #f0f0f0;font-size:13px;color:#333;font-family:{FUENTE};">{a.get("descripcion", "")}</td>'
                f'<td style="padding:10px 12px;border-bottom:1px solid #f0f0f0;font-size:13px;color:{VERDE};font-family:{FUENTE};">{a.get("responsable", "Por definir")}</td>'
                f'<td style="padding:10px 12px;border-bottom:1px solid #f0f0f0;font-size:13px;color:#c2410c;font-family:{FUENTE};white-space:nowrap;">{a.get("fecha_limite", "Sin fecha")}</td>'
                '</tr>'
            )
        filas.append(f'''<tr><td>
          <table cellpadding="0" cellspacing="0" style="width:100%;border-collapse:collapse;">
            <tr>
              <th align="left" style="background:#f8f8f8;padding:8px 12px;font-size:11px;font-weight:600;color:{GRIS};text-transform:uppercase;font-family:{FUENTE};border-bottom:2px solid #eee;">Acción</th>
              <th align="left" style="background:#f8f8f8;padding:8px 12px;font-size:11px;font-weight:600;color:{GRIS};text-transform:uppercase;font-family:{FUENTE};border-bottom:2px solid #eee;">Responsable</th>
              <th align="left" style="background:#f8f8f8;padding:8px 12px;font-size:11px;font-weight:600;color:{GRIS};text-transform:uppercase;font-family:{FUENTE};border-bottom:2px solid #eee;">Fecha límite</th>
            </tr>
            {filas_acc}
          </table>
        </td></tr>''')

    filas.append(
        f'<tr><td style="padding-top:24px;font-size:11px;color:#bbb;text-align:center;'
        f'font-family:{FUENTE};">Generado automáticamente · Meeting Notes Bot · {fecha_hoy}</td></tr>'
    )

    cuerpo = "\n".join(filas)

    return f'''<table cellpadding="0" cellspacing="0" style="width:100%;background:#f5f5f0;">
  <tr>
    <td align="center" style="padding:24px 12px;">
      <table cellpadding="0" cellspacing="0" style="width:640px;max-width:640px;background:#ffffff;border:1px solid #eee;">
        <tr><td style="padding:32px 36px;">
          <table cellpadding="0" cellspacing="0" style="width:100%;">
            {cuerpo}
          </table>
        </td></tr>
      </table>
    </td>
  </tr>
</table>'''

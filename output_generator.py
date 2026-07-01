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
    fecha_hoy  = datetime.now().strftime("%d/%m/%Y")
    fecha_hora = datetime.now().strftime("%Y%m%d_%H%M")

    es_schema_nuevo = "tipo_reunion" in notas and "secciones" in notas

    if es_schema_nuevo:
        html = _generar_html_nuevo(notas, nombre_archivo, fecha_hoy)
    else:
        html = _generar_html_legacy(notas, nombre_archivo, fecha_hoy)

    nombre_output = f"{fecha_hora}_{Path(nombre_archivo).stem[:50]}.html"
    nombre_output = "".join(c if c.isalnum() or c in "._- " else "_" for c in nombre_output)
    ruta_output   = os.path.join(output_folder, nombre_output)

    with open(ruta_output, "w", encoding="utf-8") as f:
        f.write(html)

    return ruta_output


# ─── SCHEMA NUEVO ────────────────────────────────────────────────────────────

def _generar_html_nuevo(notas: dict, nombre_archivo: str, fecha_hoy: str) -> str:
    tipo         = notas.get("tipo_reunion", "general")
    tipo_label   = TIPO_LABELS.get(tipo, tipo.capitalize())
    html_participantes = _render_chips(notas.get("participantes", []))
    html_acciones      = _render_acciones(notas.get("acciones", []))
    html_secciones     = _render_secciones(notas.get("secciones", []))

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
    .copy-btn, .reprocesar-section {{ display: none; }}
  }}
</style>
</head>
<body>
<div class="card">

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

  <button class="copy-btn" onclick="copiarContenido(this)">
    📋 Copiar todo para pegar en Loop
  </button>

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

        if tipo == "destacado":
            body = f'<div class="sec-destacado">{contenido}</div>'
        elif tipo == "texto":
            body = f'<p class="sec-texto">{contenido}</p>'
        elif tipo == "lista":
            items = contenido if isinstance(contenido, list) else [contenido]
            lis = "".join(f"<li><span>{item}</span></li>" for item in items if item)
            body = f'<ul class="sec-lista">{lis}</ul>'
        elif tipo == "lista_numerada":
            items = contenido if isinstance(contenido, list) else [contenido]
            lis = "".join(f"<li><span>{item}</span></li>" for item in items if item)
            body = f'<ol class="sec-lista-num">{lis}</ol>'
        else:
            body = f'<p class="sec-texto">{contenido}</p>'

        partes.append(f'''
  <div class="section">
    <h2>{titulo}</h2>
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
        </tr>"""
    return f"""
    <table class="acciones-table">
      <thead><tr><th>Acción</th><th>Responsable</th><th>Fecha límite</th></tr></thead>
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

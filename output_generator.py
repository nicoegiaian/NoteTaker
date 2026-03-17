"""
output_generator.py — Genera el archivo HTML de notas
El HTML resultante es fácil de copiar y pegar en Loop/OneNote/cualquier lado.
"""

import os
import logging
from pathlib import Path
from datetime import datetime

log = logging.getLogger(__name__)


def guardar_html(notas: dict, nombre_archivo: str, output_folder: str) -> str:
    """
    Genera un archivo HTML con las notas formateadas y listo para copiar en Loop.
    
    Args:
        notas:          Diccionario con las secciones generadas por Claude
        nombre_archivo: Nombre del archivo original .mp4
        output_folder:  Carpeta donde guardar el HTML
        
    Returns:
        Ruta completa al archivo HTML generado
    """
    fecha_hoy   = datetime.now().strftime("%d/%m/%Y")
    fecha_hora  = datetime.now().strftime("%Y%m%d_%H%M")
    nombre_base = Path(nombre_archivo).stem

    # Generar las secciones HTML dinámicamente
    html_acciones      = _render_acciones(notas.get("acciones", []))
    html_dependencias  = _render_dependencias(notas.get("dependencias", []))
    html_proximos      = _render_lista(notas.get("proximos_pasos", []))
    html_participantes = _render_chips(notas.get("participantes", []))
    html_pendientes    = _render_lista(notas.get("temas_pendientes", []))

    tiene_pendientes = bool(notas.get("temas_pendientes"))

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{notas.get('titulo', nombre_base)}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: #f5f5f0;
    color: #1a1a1a;
    line-height: 1.6;
    padding: 40px 20px;
  }}

  .card {{
    background: #ffffff;
    border-radius: 12px;
    padding: 40px 48px;
    max-width: 860px;
    margin: 0 auto;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
  }}

  .header {{
    border-bottom: 2px solid #f0f0f0;
    padding-bottom: 24px;
    margin-bottom: 32px;
  }}

  .proyecto-badge {{
    display: inline-block;
    background: #e8f0fe;
    color: #1a56db;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    padding: 4px 12px;
    border-radius: 20px;
    margin-bottom: 12px;
  }}

  h1 {{
    font-size: 24px;
    font-weight: 700;
    color: #111;
    margin-bottom: 8px;
    line-height: 1.3;
  }}

  .meta {{
    font-size: 13px;
    color: #888;
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
  }}

  .meta span::before {{ margin-right: 4px; }}

  h2 {{
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    color: #888;
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    gap: 8px;
  }}

  .section {{
    margin-bottom: 36px;
  }}

  .resumen {{
    font-size: 15px;
    color: #333;
    line-height: 1.75;
    background: #fafafa;
    border-left: 3px solid #1a56db;
    padding: 16px 20px;
    border-radius: 0 8px 8px 0;
  }}

  /* Tabla de acciones */
  .acciones-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
  }}

  .acciones-table th {{
    background: #f8f8f8;
    text-align: left;
    padding: 10px 14px;
    font-size: 12px;
    font-weight: 600;
    color: #666;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    border-bottom: 2px solid #eee;
  }}

  .acciones-table td {{
    padding: 12px 14px;
    border-bottom: 1px solid #f0f0f0;
    vertical-align: top;
  }}

  .acciones-table tr:last-child td {{ border-bottom: none; }}
  .acciones-table tr:hover td {{ background: #fafafa; }}

  .responsable-chip {{
    display: inline-block;
    background: #f0fdf4;
    color: #16a34a;
    border: 1px solid #bbf7d0;
    font-size: 12px;
    font-weight: 500;
    padding: 2px 10px;
    border-radius: 20px;
    white-space: nowrap;
  }}

  .fecha-chip {{
    display: inline-block;
    background: #fff7ed;
    color: #c2410c;
    border: 1px solid #fed7aa;
    font-size: 12px;
    font-weight: 500;
    padding: 2px 10px;
    border-radius: 20px;
    white-space: nowrap;
  }}

  .fecha-chip.sin-fecha {{
    background: #f8f8f8;
    color: #999;
    border-color: #e5e5e5;
  }}

  /* Dependencias */
  .dep-item {{
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 12px 16px;
    background: #fefce8;
    border: 1px solid #fde68a;
    border-radius: 8px;
    margin-bottom: 10px;
    font-size: 14px;
  }}

  .dep-item:last-child {{ margin-bottom: 0; }}

  .dep-icon {{ font-size: 16px; flex-shrink: 0; margin-top: 1px; }}

  .dep-content strong {{ display: block; color: #111; margin-bottom: 3px; }}
  .dep-content span   {{ color: #78716c; font-size: 13px; }}

  /* Próximos pasos */
  .pasos-list {{
    list-style: none;
    counter-reset: pasos;
  }}

  .pasos-list li {{
    counter-increment: pasos;
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 10px 0;
    border-bottom: 1px solid #f5f5f5;
    font-size: 14px;
  }}

  .pasos-list li:last-child {{ border-bottom: none; }}

  .pasos-list li::before {{
    content: counter(pasos);
    display: flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    background: #1a56db;
    color: white;
    border-radius: 50%;
    font-size: 12px;
    font-weight: 700;
    flex-shrink: 0;
  }}

  /* Participantes chips */
  .chips-container {{ display: flex; flex-wrap: wrap; gap: 8px; }}

  .chip {{
    background: #f3f4f6;
    color: #374151;
    border: 1px solid #e5e7eb;
    font-size: 13px;
    font-weight: 500;
    padding: 4px 12px;
    border-radius: 20px;
  }}

  /* Temas pendientes */
  .pendientes-list {{
    list-style: none;
  }}

  .pendientes-list li {{
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 8px 0;
    font-size: 14px;
    color: #555;
    border-bottom: 1px solid #f5f5f5;
  }}

  .pendientes-list li:last-child {{ border-bottom: none; }}
  .pendientes-list li::before {{ content: "⚠️"; flex-shrink: 0; }}

  .copy-btn {{
    display: block;
    width: 100%;
    padding: 14px;
    background: #1a56db;
    color: white;
    border: none;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    margin-top: 32px;
    transition: background 0.2s;
  }}

  .copy-btn:hover {{ background: #1e429f; }}
  .copy-btn.copied {{ background: #16a34a; }}

  .footer {{
    text-align: center;
    font-size: 12px;
    color: #bbb;
    margin-top: 20px;
  }}

  @media print {{
    body {{ background: white; padding: 0; }}
    .card {{ box-shadow: none; padding: 20px; }}
    .copy-btn {{ display: none; }}
  }}
</style>
</head>
<body>
<div class="card">

  <div class="header">
    <div class="proyecto-badge">{notas.get('proyecto', 'Sin proyecto')}</div>
    <h1>{notas.get('titulo', nombre_base)}</h1>
    <div class="meta">
      <span>📅 {fecha_hoy}</span>
      <span>📂 {nombre_archivo}</span>
    </div>
  </div>

  <div class="section">
    <h2>📋 Resumen</h2>
    <p class="resumen">{notas.get('resumen', 'Sin resumen disponible.')}</p>
  </div>

  {"" if not notas.get('participantes') else f'''
  <div class="section">
    <h2>👥 Participantes</h2>
    <div class="chips-container">{html_participantes}</div>
  </div>
  '''}

  <div class="section">
    <h2>✅ Acciones</h2>
    {html_acciones}
  </div>

  {"" if not notas.get('dependencias') else f'''
  <div class="section">
    <h2>🔗 Dependencias</h2>
    {html_dependencias}
  </div>
  '''}

  <div class="section">
    <h2>🚀 Próximos Pasos</h2>
    {html_proximos}
  </div>

  {"" if not tiene_pendientes else f'''
  <div class="section">
    <h2>⚠️ Temas Pendientes</h2>
    <ul class="pendientes-list">{html_pendientes}</ul>
  </div>
  '''}

  <button class="copy-btn" onclick="copiarContenido(this)">
    📋 Copiar todo para pegar en Loop
  </button>

</div>

<div class="footer">
  Generado automáticamente · Meeting Notes Bot · {fecha_hoy}
</div>

<script>
function copiarContenido(btn) {{
  // Selecciona el contenido de la card (sin el botón)
  const card = document.querySelector('.card');
  const boton = card.querySelector('.copy-btn');
  boton.style.display = 'none';

  const range = document.createRange();
  range.selectNode(card);
  window.getSelection().removeAllRanges();
  window.getSelection().addRange(range);
  document.execCommand('copy');
  window.getSelection().removeAllRanges();

  boton.style.display = 'block';
  btn.textContent = '✅ Copiado — ahora pegalo en Loop (Ctrl+V)';
  btn.classList.add('copied');
  setTimeout(() => {{
    btn.textContent = '📋 Copiar todo para pegar en Loop';
    btn.classList.remove('copied');
  }}, 4000);
}}
</script>
</body>
</html>"""

    # Guardar el archivo
    nombre_output = f"{fecha_hora}_{Path(nombre_archivo).stem[:50]}.html"
    # Reemplazar caracteres no válidos para nombres de archivo
    nombre_output = "".join(c if c.isalnum() or c in "._- " else "_" for c in nombre_output)
    ruta_output   = os.path.join(output_folder, nombre_output)

    with open(ruta_output, "w", encoding="utf-8") as f:
        f.write(html)

    return ruta_output


def _render_acciones(acciones: list) -> str:
    if not acciones:
        return '<p style="color:#888;font-size:14px;">No se identificaron acciones específicas.</p>'

    filas = ""
    for a in acciones:
        tiene_fecha = a.get("fecha_limite", "Sin fecha definida") != "Sin fecha definida"
        clase_fecha = "fecha-chip" if tiene_fecha else "fecha-chip sin-fecha"
        filas += f"""
        <tr>
          <td>{a.get('descripcion', '')}</td>
          <td><span class="responsable-chip">{a.get('responsable', 'Por definir')}</span></td>
          <td><span class="{clase_fecha}">{a.get('fecha_limite', 'Sin fecha')}</span></td>
        </tr>"""

    return f"""
    <table class="acciones-table">
      <thead>
        <tr>
          <th>Acción</th>
          <th>Responsable</th>
          <th>Fecha límite</th>
        </tr>
      </thead>
      <tbody>{filas}</tbody>
    </table>"""


def _render_dependencias(dependencias: list) -> str:
    if not dependencias:
        return ""
    items = ""
    for d in dependencias:
        items += f"""
        <div class="dep-item">
          <span class="dep-icon">⛓️</span>
          <div class="dep-content">
            <strong>{d.get('descripcion', '')}</strong>
            <span>Depende de: {d.get('depende_de', 'No especificado')}</span>
          </div>
        </div>"""
    return items


def _render_lista(items: list) -> str:
    if not items:
        return '<p style="color:#888;font-size:14px;">No hay ítems registrados.</p>'
    lis = "".join(f"<li>{item}</li>" for item in items)
    return f'<ol class="pasos-list">{lis}</ol>'


def _render_chips(items: list) -> str:
    return "".join(f'<span class="chip">{item}</span>' for item in items)

"""Exporter — JSON, CSV (ZIP) and self-contained HTML report."""
from __future__ import annotations

import csv
import io
import json
import zipfile
from typing import Any

from .models import ScanResults


def export_json(results: ScanResults) -> str:
    """Return scan results as a JSON string."""
    return results.model_dump_json(indent=2)


def export_csv_zip(results: ScanResults) -> bytes:
    """Return a ZIP archive containing three CSV files."""
    buf = io.BytesIO()

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Pages CSV
        pages_io = io.StringIO()
        writer = csv.writer(pages_io)
        writer.writerow(["URL", "Status", "Size", "Title", "Depth", "Links", "Forms", "Error"])
        for p in results.pages:
            writer.writerow([p.url, p.status_code, p.content_length, p.title or "", p.depth, p.links_found, p.forms_found, p.error or ""])
        zf.writestr("pages.csv", pages_io.getvalue())

        # Fuzz CSV
        fuzz_io = io.StringIO()
        writer = csv.writer(fuzz_io)
        writer.writerow(["URL", "Path", "Status", "Size", "Redirect"])
        for f in results.fuzz_results:
            writer.writerow([f.url, f.path, f.status_code, f.content_length, f.redirect_url or ""])
        zf.writestr("fuzz_results.csv", fuzz_io.getvalue())

        # Forms CSV
        forms_io = io.StringIO()
        writer = csv.writer(forms_io)
        writer.writerow(["Page", "Action", "Method", "Type", "Fields", "CSRF", "CSRF Field"])
        for fm in results.forms:
            writer.writerow([
                fm.page_url, fm.action or "", fm.method, fm.form_type.value,
                len(fm.fields), fm.has_csrf_token, fm.csrf_field_name or "",
            ])
        zf.writestr("forms.csv", forms_io.getvalue())

    return buf.getvalue()


def export_html(results: ScanResults) -> str:
    """Return a self-contained HTML report with embedded Cytoscape.js and Chart.js."""
    data = results.model_dump()

    # Build Cytoscape elements
    cy_elements: list[dict[str, Any]] = []
    for node in data["nodes"]:
        cy_elements.append({
            "data": {
                "id": node["id"],
                "label": node["label"],
                "node_type": node["node_type"],
                "status_code": node.get("status_code"),
                **node.get("metadata", {}),
            }
        })
    for edge in data["edges"]:
        cy_elements.append({
            "data": {
                "source": edge["source"],
                "target": edge["target"],
                "edge_type": edge["edge_type"],
                "label": edge.get("label", ""),
            }
        })

    # Status distribution
    status_dist: dict[str, int] = {}
    for p in data["pages"]:
        group = f"{p['status_code'] // 100}xx"
        status_dist[group] = status_dist.get(group, 0) + 1
    for f in data["fuzz_results"]:
        group = f"{f['status_code'] // 100}xx"
        status_dist[group] = status_dist.get(group, 0) + 1

    # Form type distribution
    form_dist: dict[str, int] = {}
    for fm in data["forms"]:
        ft = fm["form_type"]
        form_dist[ft] = form_dist.get(ft, 0) + 1

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WebMapper — Informe de Escaneo</title>
<script src="https://unpkg.com/cytoscape@3.28.1/dist/cytoscape.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0a0a1a; --surface: #1a1a2e; --text: #e0e0e0; --accent: #00d4ff;
    --green: #10b981; --yellow: #f59e0b; --red: #ef4444; --purple: #7c3aed;
  }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:'Segoe UI',system-ui,sans-serif; background:var(--bg); color:var(--text); padding:24px; }}
  h1 {{ color:var(--accent); margin-bottom:8px; }}
  h2 {{ color:var(--accent); margin:24px 0 12px; font-size:1.3rem; }}
  .meta {{ color:#888; margin-bottom:24px; }}
  #cy {{ width:100%; height:500px; background:var(--surface); border-radius:12px; border:1px solid #333; }}
  .charts {{ display:grid; grid-template-columns:1fr 1fr; gap:24px; margin:24px 0; }}
  .chart-box {{ background:var(--surface); border-radius:12px; padding:16px; border:1px solid #333; }}
  canvas {{ max-height:300px; }}
  table {{ width:100%; border-collapse:collapse; margin:12px 0; }}
  th, td {{ padding:8px 12px; text-align:left; border-bottom:1px solid #333; font-size:0.9rem; }}
  th {{ background:#16213e; color:var(--accent); position:sticky; top:0; }}
  tr:hover {{ background:#16213e44; }}
  .badge {{ padding:2px 8px; border-radius:4px; font-size:0.8rem; font-weight:600; }}
  .badge-2xx {{ background:#10b98133; color:#10b981; }}
  .badge-3xx {{ background:#f59e0b33; color:#f59e0b; }}
  .badge-4xx {{ background:#f97316aa; color:#fff; }}
  .badge-5xx {{ background:#ef444488; color:#fff; }}
</style>
</head>
<body>
<h1>🗺️ WebMapper — Informe</h1>
<p class="meta">URL: {data['config']['url']} | Profundidad: {data['config']['depth']} | Páginas: {len(data['pages'])} | Formularios: {len(data['forms'])} | Fuzzing: {len(data['fuzz_results'])} rutas</p>

<h2>Grafo de la Aplicación</h2>
<div id="cy"></div>

<div class="charts">
  <div class="chart-box"><canvas id="statusChart"></canvas></div>
  <div class="chart-box"><canvas id="formChart"></canvas></div>
</div>

<h2>Páginas Visitadas</h2>
<table>
<thead><tr><th>URL</th><th>Estado</th><th>Tamaño</th><th>Título</th><th>Prof.</th><th>Enlaces</th><th>Forms</th></tr></thead>
<tbody>
{"".join(f'<tr><td>{p["url"]}</td><td><span class="badge badge-{p["status_code"]//100}xx">{p["status_code"]}</span></td><td>{p["content_length"]}</td><td>{p.get("title","")}</td><td>{p["depth"]}</td><td>{p["links_found"]}</td><td>{p["forms_found"]}</td></tr>' for p in data["pages"])}
</tbody></table>

{"<h2>Rutas Descubiertas (Fuzzing)</h2><table><thead><tr><th>Ruta</th><th>Estado</th><th>Tamaño</th><th>Redirección</th></tr></thead><tbody>" + "".join(f'<tr><td>{f["path"]}</td><td><span class="badge badge-{f["status_code"]//100}xx">{f["status_code"]}</span></td><td>{f["content_length"]}</td><td>{f.get("redirect_url","")}</td></tr>' for f in data["fuzz_results"]) + "</tbody></table>" if data["fuzz_results"] else ""}

<h2>Formularios</h2>
<table>
<thead><tr><th>Página</th><th>Acción</th><th>Método</th><th>Tipo</th><th>Campos</th><th>CSRF</th></tr></thead>
<tbody>
{"".join(f'<tr><td>{fm["page_url"]}</td><td>{fm.get("action","")}</td><td>{fm["method"].upper()}</td><td>{fm["form_type"]}</td><td>{len(fm["fields"])}</td><td>{"✅" if fm["has_csrf_token"] else "❌"}</td></tr>' for fm in data["forms"])}
</tbody></table>

<script>
const elements = {json.dumps(cy_elements)};
const cy = cytoscape({{
  container: document.getElementById('cy'),
  elements: elements,
  style: [
    {{ selector: 'node', style: {{ 'label': 'data(label)', 'font-size': '10px', 'color': '#e0e0e0', 'text-valign': 'bottom', 'text-margin-y': 4, 'width': 28, 'height': 28 }} }},
    {{ selector: 'node[node_type="page"]', style: {{ 'background-color': '#10b981', 'shape': 'ellipse' }} }},
    {{ selector: 'node[node_type="fuzzed"]', style: {{ 'background-color': '#f59e0b', 'shape': 'diamond' }} }},
    {{ selector: 'node[node_type="form"]', style: {{ 'background-color': '#7c3aed', 'shape': 'rectangle' }} }},
    {{ selector: 'node[node_type="external"]', style: {{ 'background-color': '#ef4444', 'shape': 'triangle' }} }},
    {{ selector: 'edge', style: {{ 'width': 1.5, 'line-color': '#555', 'target-arrow-color': '#555', 'target-arrow-shape': 'triangle', 'curve-style': 'bezier', 'arrow-scale': 0.8 }} }},
  ],
  layout: {{ name: 'cose', animate: false, padding: 30 }},
}});

const statusDist = {json.dumps(status_dist)};
const formDist = {json.dumps(form_dist)};
const colors = {{ '2xx': '#10b981', '3xx': '#f59e0b', '4xx': '#f97316', '5xx': '#ef4444' }};
const formColors = {{ login: '#ef4444', search: '#00d4ff', upload: '#f59e0b', other: '#7c3aed' }};

new Chart(document.getElementById('statusChart'), {{
  type: 'bar',
  data: {{ labels: Object.keys(statusDist), datasets: [{{ label: 'Códigos HTTP', data: Object.values(statusDist), backgroundColor: Object.keys(statusDist).map(k => colors[k] || '#666') }}] }},
  options: {{ plugins: {{ legend: {{ display: false }} }}, scales: {{ y: {{ beginAtZero: true, ticks: {{ color: '#888' }} }}, x: {{ ticks: {{ color: '#888' }} }} }} }}
}});

new Chart(document.getElementById('formChart'), {{
  type: 'doughnut',
  data: {{ labels: Object.keys(formDist), datasets: [{{ data: Object.values(formDist), backgroundColor: Object.keys(formDist).map(k => formColors[k] || '#666') }}] }},
  options: {{ plugins: {{ legend: {{ labels: {{ color: '#e0e0e0' }} }} }} }}
}});
</script>
</body></html>"""

    return html

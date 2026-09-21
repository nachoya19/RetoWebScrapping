/**
 * export.js — Download results in JSON, CSV, or HTML
 */
const Export = (() => {
  function init() {
    document.getElementById('exportJson')?.addEventListener('click', () => download('json'));
    document.getElementById('exportCsv')?.addEventListener('click', () => download('csv'));
    document.getElementById('exportHtml')?.addEventListener('click', () => download('html'));
  }

  async function download(format) {
    const btn = document.getElementById(`export${format.charAt(0).toUpperCase() + format.slice(1)}`);
    if (btn) {
      btn.style.opacity = '0.6';
      btn.style.pointerEvents = 'none';
    }

    try {
      const resp = await fetch(`/api/export/${format}`);
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ error: 'Error desconocido' }));
        alert(err.error || 'No hay resultados para exportar');
        return;
      }

      const blob = await resp.blob();
      const exts = { json: 'json', csv: 'zip', html: 'html' };
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `webmapper_report.${exts[format] || format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(a.href);
    } catch (err) {
      alert('Error al exportar: ' + err.message);
    } finally {
      if (btn) {
        btn.style.opacity = '1';
        btn.style.pointerEvents = '';
      }
    }
  }

  return { init };
})();

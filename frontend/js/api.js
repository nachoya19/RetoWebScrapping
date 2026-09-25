/**
 * api.js — Capa de comunicación con el backend (fetch / SSE)
 */

/**
 * Sube un wordlist personalizado al backend.
 * @param {File} file
 * @returns {Promise<Response>}
 */
export async function uploadWordlist(file) {
  const formData = new FormData();
  formData.append('file', file);
  return fetch('/api/wordlist', { method: 'POST', body: formData });
}

/**
 * Inicia un escaneo con la configuración dada.
 * @param {object} config
 * @returns {Promise<{ok: boolean, status: number, data: any}>}
 */
export async function startScan(config) {
  const resp = await fetch('/api/scan/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
  const data = await resp.json();
  return { ok: resp.ok, status: resp.status, data };
}

/**
 * Detiene el escaneo en curso.
 * @returns {Promise<Response>}
 */
export async function stopScan() {
  return fetch('/api/scan/stop', { method: 'POST' });
}

/**
 * Obtiene los resultados del último escaneo.
 * @returns {Promise<{ok: boolean, data: any}>}
 */
export async function fetchResults() {
  const resp = await fetch('/api/results');
  if (!resp.ok) return { ok: false, data: null };
  const data = await resp.json();
  return { ok: true, data };
}

/**
 * Consulta el estado actual del escaneo (running / has_results).
 * @returns {Promise<any>}
 */
export async function fetchScanStatus() {
  const resp = await fetch('/api/scan/status');
  return resp.json();
}

/**
 * Abre la conexión SSE de progreso de escaneo.
 * @returns {EventSource}
 */
export function createProgressStream() {
  return new EventSource('/api/scan/progress');
}

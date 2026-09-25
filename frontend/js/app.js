/**
 * app.js — Main controller: tabs, form, SSE, orchestration
 */
(() => {
  'use strict';

  // ── Tab navigation ─────────────────────────
  const tabBtns = document.querySelectorAll('.tab-btn');
  const panels  = document.querySelectorAll('.panel');

  function switchTab(tabId) {
    tabBtns.forEach(b => b.classList.toggle('active', b.dataset.tab === tabId));
    panels.forEach(p => p.classList.toggle('active', p.id === `panel-${tabId}`));
  }

  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });

  // ── Result sub-tabs ────────────────────────
  document.querySelectorAll('.rtab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.rtab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.result-section').forEach(s => s.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById(`rtab-${btn.dataset.rtab}`)?.classList.add('active');
    });
  });

  // ── Depth slider value ─────────────────────
  const depthSlider = document.getElementById('spiderDepth');
  const depthValue  = document.getElementById('depthValue');
  depthSlider?.addEventListener('input', () => {
    depthValue.textContent = depthSlider.value;
  });

  // ── Toggle fuzzing options ─────────────────
  const fuzzToggle  = document.getElementById('enableFuzzing');
  const fuzzOptions = document.getElementById('fuzzOptions');
  fuzzToggle?.addEventListener('change', () => {
    fuzzOptions?.classList.toggle('hidden', !fuzzToggle.checked);
  });

  // ── File upload label ──────────────────────
  const wordlistInput = document.getElementById('wordlistUpload');
  const fileLabel     = document.getElementById('fileLabel');
  wordlistInput?.addEventListener('change', () => {
    if (wordlistInput.files.length > 0) {
      fileLabel.textContent = wordlistInput.files[0].name;
      fileLabel.style.color = '#10b981';
    }
  });

  // ── Header status ──────────────────────────
  const statusDot  = document.querySelector('.status-dot');
  const statusText = document.querySelector('.status-text');

  function setStatus(state, text) {
    statusDot.className = 'status-dot';
    if (state === 'scanning') statusDot.classList.add('scanning');
    if (state === 'error')    statusDot.classList.add('error');
    statusText.textContent = text;
  }

  // ── Log output ─────────────────────────────
  const logOutput = document.getElementById('logOutput');

  function addLog(message, type = 'info') {
    const line = document.createElement('div');
    line.className = `log-line log-${type}`;
    const now = new Date().toLocaleTimeString();
    line.textContent = `[${now}] ${message}`;
    logOutput.appendChild(line);
    logOutput.scrollTop = logOutput.scrollHeight;
  }

  // ── Stats ──────────────────────────────────
  const statPages  = document.getElementById('statPages');
  const statForms  = document.getElementById('statForms');
  const statFuzzed = document.getElementById('statFuzzed');
  const statPhase  = document.getElementById('statPhase');

  let pagesCount = 0;
  let formsCount = 0;
  let fuzzCount  = 0;

  // ── Progress ───────────────────────────────
  const progressBar  = document.getElementById('progressBar');
  const progressText = document.getElementById('progressText');
  const progressSub  = document.getElementById('progressSubtitle');

  // ── Buttons & Checkbox ─────────────────────
  const btnStart    = document.getElementById('btnStart');
  const btnStop     = document.getElementById('btnStop');
  const authConfirm = document.getElementById('authConfirm');

  if (authConfirm && btnStart) {
    const updateButtonState = () => {
      btnStart.disabled = !authConfirm.checked;
    };

    updateButtonState();

    authConfirm.addEventListener('change', updateButtonState);
  }

  // ── Scan form submit ───────────────────────
  const scanForm = document.getElementById('scanForm');

  scanForm?.addEventListener('submit', async (e) => {
    e.preventDefault();

    // Upload custom wordlist if selected
    if (wordlistInput?.files.length > 0) {
      const formData = new FormData();
      formData.append('file', wordlistInput.files[0]);
      try {
        await fetch('/api/wordlist', { method: 'POST', body: formData });
        addLog('Diccionario personalizado cargado', 'success');
      } catch (err) {
        addLog('Error al subir diccionario: ' + err.message, 'error');
      }
    }

    const config = {
      url: document.getElementById('targetUrl').value.trim(),
      depth: parseInt(depthSlider.value),
      max_pages: parseInt(document.getElementById('maxPages').value),
      request_delay: parseFloat(document.getElementById('requestDelay').value),
      include_subdomains: document.getElementById('includeSubdomains').checked,
      enable_fuzzing: fuzzToggle.checked,
      authorized: document.getElementById('authConfirm').checked,
      fuzz_concurrency: parseInt(document.getElementById('fuzzConcurrency')?.value || '5'),
      fuzz_extensions: (document.getElementById('fuzzExtensions')?.value || '')
        .split(',')
        .map(s => s.trim())
        .filter(Boolean),
    };

    // Start scan
    try {
      const resp = await fetch('/api/scan/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      const data = await resp.json();

      if (!resp.ok) {
        addLog(`Error: ${data.error}`, 'error');
        alert(data.error);
        return;
      }

      // Switch to progress tab
      switchTab('progress');
      resetProgress();
      setStatus('scanning', 'Escaneando…');
      btnStart.classList.add('hidden');
      btnStop.classList.remove('hidden');

      addLog(`Escaneo iniciado: ${config.url}`, 'info');
      addLog(`Profundidad: ${config.depth} | Max páginas: ${config.max_pages} | Fuzzing: ${config.enable_fuzzing ? 'Sí' : 'No'}`, 'info');

      // Connect SSE
      connectSSE();

    } catch (err) {
      addLog('Error al iniciar: ' + err.message, 'error');
      setStatus('error', 'Error');
    }
  });

  // ── Stop button ────────────────────────────
  btnStop?.addEventListener('click', async () => {
    try {
      await fetch('/api/scan/stop', { method: 'POST' });
      addLog('Deteniendo escaneo…', 'info');
    } catch (err) {
      addLog('Error al detener: ' + err.message, 'error');
    }
  });

  // ── SSE connection ─────────────────────────
  let evtSource = null;

  function connectSSE() {
    if (evtSource) evtSource.close();
    evtSource = new EventSource('/api/scan/progress');

    evtSource.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      handleProgress(msg);
    };

    evtSource.onerror = () => {
      evtSource.close();
      evtSource = null;
    };
  }

  function handleProgress(msg) {
    switch (msg.type) {
      case 'spider':
        handleSpider(msg);
        break;
      case 'fuzzer':
        handleFuzzer(msg);
        break;
      case 'scan':
        handleScan(msg);
        break;
    }
  }

  function handleSpider(msg) {
    statPhase.textContent = 'Spider';

    if (msg.status === 'visiting') {
      pagesCount = msg.visited;
      statPages.textContent = pagesCount;
      const pct = Math.round((msg.visited / msg.max_pages) * 100);
      progressBar.style.width = pct + '%';
      progressText.textContent = `${pct}% — ${msg.visited}/${msg.max_pages} páginas`;
      progressSub.textContent = `Visitando: ${msg.url}`;
      addLog(`[Spider] Profundidad ${msg.depth}: ${msg.url}`, 'spider');
    }
  }

  function handleFuzzer(msg) {
    statPhase.textContent = 'Fuzzer';

    if (msg.status === 'starting') {
      addLog(`[Fuzzer] Iniciando — ${msg.total_paths} rutas a probar`, 'fuzzer');
    } else if (msg.status === 'found') {
      fuzzCount++;
      statFuzzed.textContent = fuzzCount;
      addLog(`[Fuzzer] ✓ ${msg.path} → ${msg.status_code}`, 'fuzzer');
    } else if (msg.status === 'progress') {
      const pct = Math.round((msg.done / msg.total) * 100);
      progressBar.style.width = pct + '%';
      progressText.textContent = `${pct}% — Fuzzing ${msg.done}/${msg.total}`;
    } else if (msg.status === 'finished') {
      addLog(`[Fuzzer] Finalizado — ${msg.found} rutas encontradas`, 'success');
    }
  }

  function handleScan(msg) {
    if (msg.status === 'starting') {
      addLog(`Fase: ${msg.phase}`, 'info');
      statPhase.textContent = msg.phase === 'spider' ? 'Spider' : 'Fuzzer';
    } else if (msg.status === 'building_graph') {
      addLog('Construyendo grafo…', 'info');
      statPhase.textContent = 'Grafo';
    } else if (msg.status === 'finished') {
      addLog(`✅ Escaneo completado — ${msg.pages_count} páginas, ${msg.forms_count} formularios, ${msg.fuzz_count} rutas fuzz`, 'success');
      setStatus('ready', 'Completado');
      statPages.textContent = msg.pages_count;
      statForms.textContent = msg.forms_count;
      statFuzzed.textContent = msg.fuzz_count;
      statPhase.textContent = '✅';
      progressBar.style.width = '100%';
      progressText.textContent = '100% — Completado';
      progressSub.textContent = 'Escaneo finalizado';

      btnStart.classList.remove('hidden');
      btnStop.classList.add('hidden');

      if (evtSource) { evtSource.close(); evtSource = null; }

      // Load results
      loadResults();
    } else if (msg.status === 'error') {
      addLog(`❌ Error: ${msg.message}`, 'error');
      setStatus('error', 'Error');
      btnStart.classList.remove('hidden');
      btnStop.classList.add('hidden');
      if (evtSource) { evtSource.close(); evtSource = null; }
    }
  }

  // ── Load results into UI ───────────────────
  async function loadResults() {
    try {
      const resp = await fetch('/api/results');
      if (!resp.ok) return;
      const data = await resp.json();

      // Initialize all modules
      Tables.init(data);
      Graph.init(data);
      Charts.init(data);
      Export.init();

      addLog('Resultados cargados en la interfaz', 'success');
    } catch (err) {
      addLog('Error al cargar resultados: ' + err.message, 'error');
    }
  }

  // ── Reset progress ─────────────────────────
  function resetProgress() {
    pagesCount = 0;
    formsCount = 0;
    fuzzCount  = 0;
    statPages.textContent = '0';
    statForms.textContent = '0';
    statFuzzed.textContent = '0';
    statPhase.textContent = '—';
    progressBar.style.width = '0%';
    progressText.textContent = '0%';
    progressSub.textContent = 'Iniciando…';
    logOutput.innerHTML = '';
  }

  // ── Init export on page load (for refresh after scan) ──
  Export.init();

  // ── Check for existing results on load ─────
  (async () => {
    try {
      const resp = await fetch('/api/scan/status');
      const status = await resp.json();
      if (status.has_results) {
        loadResults();
        setStatus('ready', 'Resultados disponibles');
      }
    } catch (e) { /* ignore */ }
  })();
})();

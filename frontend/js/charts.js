/**
 * charts.js — Chart.js distribution charts
 */
const Charts = (() => {
  // Shared defaults for dark theme
  const darkDefaults = {
    color: '#e4e4ed',
    borderColor: '#2a2a4a',
  };

  const STATUS_COLORS = {
    '1xx': '#00d4ff',
    '2xx': '#10b981',
    '3xx': '#f59e0b',
    '4xx': '#f97316',
    '5xx': '#ef4444',
  };

  const FORM_COLORS = {
    login:  '#ef4444',
    search: '#00d4ff',
    upload: '#f59e0b',
    other:  '#7c3aed',
  };

  const DOMAIN_PALETTE = [
    '#00d4ff', '#7c3aed', '#10b981', '#f59e0b', '#ef4444',
    '#ec4899', '#06b6d4', '#8b5cf6', '#14b8a6', '#f97316',
  ];

  // Keep references to destroy on re-init
  let chartInstances = [];

  function destroyAll() {
    chartInstances.forEach(c => c.destroy());
    chartInstances = [];
  }

  function init(data) {
    destroyAll();

    // Set Chart.js defaults for dark mode
    Chart.defaults.color = '#9999b3';
    Chart.defaults.borderColor = '#2a2a4a';

    renderStatusChart(data);
    renderFormTypesChart(data);
    renderDomainsChart(data);
    renderDepthChart(data);
  }

  /** HTTP status distribution */
  function renderStatusChart(data) {
    const canvas = document.getElementById('chartStatus');
    if (!canvas) return;

    const dist = {};
    (data.pages || []).forEach(p => {
      const g = Math.floor(p.status_code / 100) + 'xx';
      dist[g] = (dist[g] || 0) + 1;
    });
    (data.fuzz_results || []).forEach(f => {
      const g = Math.floor(f.status_code / 100) + 'xx';
      dist[g] = (dist[g] || 0) + 1;
    });

    const labels = Object.keys(dist).sort();
    const values = labels.map(l => dist[l]);
    const colors = labels.map(l => STATUS_COLORS[l] || '#666');

    const chart = new Chart(canvas, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: 'Cantidad',
          data: values,
          backgroundColor: colors,
          borderColor: colors.map(c => c + '88'),
          borderWidth: 1,
          borderRadius: 6,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: { display: false },
          title: { display: false },
        },
        scales: {
          y: { beginAtZero: true, ticks: { stepSize: 1 }, grid: { color: '#2a2a4a33' } },
          x: { grid: { display: false } },
        },
      },
    });
    chartInstances.push(chart);
  }

  /** Form types distribution */
  function renderFormTypesChart(data) {
    const canvas = document.getElementById('chartFormTypes');
    if (!canvas) return;

    const dist = {};
    (data.forms || []).forEach(fm => {
      const t = fm.form_type;
      dist[t] = (dist[t] || 0) + 1;
    });

    const labels = Object.keys(dist);
    const values = labels.map(l => dist[l]);
    const colors = labels.map(l => FORM_COLORS[l] || '#666');

    if (labels.length === 0) {
      labels.push('Sin formularios');
      values.push(0);
      colors.push('#333');
    }

    const chart = new Chart(canvas, {
      type: 'doughnut',
      data: {
        labels,
        datasets: [{
          data: values,
          backgroundColor: colors,
          borderColor: '#0a0a1a',
          borderWidth: 3,
          hoverOffset: 8,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        cutout: '55%',
        plugins: {
          legend: {
            position: 'bottom',
            labels: { padding: 16, usePointStyle: true, pointStyleWidth: 10 },
          },
        },
      },
    });
    chartInstances.push(chart);
  }

  /** Resources per domain */
  function renderDomainsChart(data) {
    const canvas = document.getElementById('chartDomains');
    if (!canvas) return;

    const dist = {};
    (data.pages || []).forEach(p => {
      try {
        const domain = new URL(p.url).hostname;
        dist[domain] = (dist[domain] || 0) + 1;
      } catch (e) { /* skip */ }
    });

    const labels = Object.keys(dist);
    const values = labels.map(l => dist[l]);
    const colors = labels.map((_, i) => DOMAIN_PALETTE[i % DOMAIN_PALETTE.length]);

    if (labels.length === 0) {
      labels.push('Sin datos');
      values.push(0);
      colors.push('#333');
    }

    const chart = new Chart(canvas, {
      type: 'doughnut',
      data: {
        labels,
        datasets: [{
          data: values,
          backgroundColor: colors,
          borderColor: '#0a0a1a',
          borderWidth: 3,
          hoverOffset: 8,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        cutout: '55%',
        plugins: {
          legend: {
            position: 'bottom',
            labels: { padding: 16, usePointStyle: true, pointStyleWidth: 10 },
          },
        },
      },
    });
    chartInstances.push(chart);
  }

  /** Pages by depth */
  function renderDepthChart(data) {
    const canvas = document.getElementById('chartDepth');
    if (!canvas) return;

    const dist = {};
    (data.pages || []).forEach(p => {
      const d = `Profundidad ${p.depth}`;
      dist[d] = (dist[d] || 0) + 1;
    });

    const labels = Object.keys(dist).sort();
    const values = labels.map(l => dist[l]);

    const chart = new Chart(canvas, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: 'Páginas',
          data: values,
          backgroundColor: '#00d4ff44',
          borderColor: '#00d4ff',
          borderWidth: 2,
          borderRadius: 6,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: { display: false },
        },
        scales: {
          y: { beginAtZero: true, ticks: { stepSize: 1 }, grid: { color: '#2a2a4a33' } },
          x: { grid: { display: false } },
        },
      },
    });
    chartInstances.push(chart);
  }

  return { init };
})();

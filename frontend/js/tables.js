/**
 * tables.js — Searchable, sortable data tables
 */
const Tables = (() => {
  /** Create a status badge HTML */
  function statusBadge(code) {
    if (!code) return '<span class="badge">—</span>';
    const group = Math.floor(code / 100);
    return `<span class="badge badge-${group}xx">${code}</span>`;
  }

  /** Create a form-type badge */
  function formTypeBadge(type) {
    const labels = { login: '🔐 Login', search: '🔍 Búsqueda', upload: '📁 Upload', other: '📝 Otro' };
    return `<span class="badge badge-${type}">${labels[type] || type}</span>`;
  }

  /** Truncate long text */
  function truncate(text, max = 60) {
    if (!text) return '';
    return text.length > max ? text.slice(0, max) + '…' : text;
  }

  /** Render pages table */
  function renderPages(pages, tbody) {
    tbody.innerHTML = pages.map(p => `
      <tr>
        <td title="${p.url}">${truncate(p.url)}</td>
        <td>${statusBadge(p.status_code)}</td>
        <td>${(p.content_length / 1024).toFixed(1)} KB</td>
        <td title="${p.title || ''}">${truncate(p.title || '—')}</td>
        <td>${p.depth}</td>
        <td>${p.links_found}</td>
        <td>${p.forms_found}</td>
      </tr>
    `).join('');
  }

  /** Render fuzz table */
  function renderFuzz(fuzzResults, tbody) {
    tbody.innerHTML = fuzzResults.map(f => `
      <tr>
        <td title="${f.url}">${f.path}</td>
        <td>${statusBadge(f.status_code)}</td>
        <td>${(f.content_length / 1024).toFixed(1)} KB</td>
        <td title="${f.redirect_url || ''}">${truncate(f.redirect_url || '—')}</td>
      </tr>
    `).join('');
  }

  /** Render forms table */
  function renderForms(forms, tbody) {
    tbody.innerHTML = forms.map(fm => `
      <tr>
        <td title="${fm.page_url}">${truncate(fm.page_url)}</td>
        <td title="${fm.action || ''}">${truncate(fm.action || '—')}</td>
        <td><span class="badge">${fm.method.toUpperCase()}</span></td>
        <td>${formTypeBadge(fm.form_type)}</td>
        <td>${fm.fields.length}</td>
        <td>${fm.has_csrf_token ? '✅' : '❌'}</td>
      </tr>
    `).join('');
  }

  /** Setup search filtering */
  function setupSearch(inputId, tableId, dataKey) {
    const input = document.getElementById(inputId);
    if (!input) return;

    input.addEventListener('input', () => {
      const query = input.value.toLowerCase();
      const rows = document.querySelectorAll(`#${tableId} tbody tr`);
      rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(query) ? '' : 'none';
      });
    });
  }

  /** Setup column sorting */
  function setupSort(tableId, allData, renderFn) {
    const table = document.getElementById(tableId);
    if (!table) return;

    let sortCol = null;
    let sortAsc = true;

    table.querySelectorAll('th[data-sort]').forEach(th => {
      th.addEventListener('click', () => {
        const key = th.dataset.sort;
        if (sortCol === key) {
          sortAsc = !sortAsc;
        } else {
          sortCol = key;
          sortAsc = true;
        }

        const sorted = [...allData].sort((a, b) => {
          let va = a[key] ?? '';
          let vb = b[key] ?? '';
          if (typeof va === 'number' && typeof vb === 'number') {
            return sortAsc ? va - vb : vb - va;
          }
          va = String(va).toLowerCase();
          vb = String(vb).toLowerCase();
          return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
        });

        renderFn(sorted, table.querySelector('tbody'));
      });
    });
  }

  /** Initialize all tables with data */
  function init(data) {
    // Pages
    const pagesTbody = document.querySelector('#tablePages tbody');
    if (pagesTbody && data.pages) {
      renderPages(data.pages, pagesTbody);
      setupSearch('searchPages', 'tablePages');
      setupSort('tablePages', data.pages, renderPages);
    }

    // Fuzz
    const fuzzTbody = document.querySelector('#tableFuzz tbody');
    if (fuzzTbody && data.fuzz_results) {
      renderFuzz(data.fuzz_results, fuzzTbody);
      setupSearch('searchFuzz', 'tableFuzz');
      setupSort('tableFuzz', data.fuzz_results, renderFuzz);
    }

    // Forms
    const formsTbody = document.querySelector('#tableForms tbody');
    if (formsTbody && data.forms) {
      renderForms(data.forms, formsTbody);
      setupSearch('searchForms', 'tableForms');
      setupSort('tableForms', data.forms, renderForms);
    }
  }

  return { init };
})();

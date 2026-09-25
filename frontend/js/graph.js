/**
 * graph.js — Cytoscape.js graph + tree visualization
 */
const Graph = (() => {
  let cy = null;
  let allElements = [];

  const NODE_COLORS = {
    page:     '#10b981',
    fuzzed:   '#f59e0b',
    form:     '#7c3aed',
    external: '#ef4444',
  };

  const NODE_SHAPES = {
    page:     'ellipse',
    fuzzed:   'diamond',
    form:     'round-rectangle',
    external: 'triangle',
  };

  /** Initialize the graph */
  function init(data) {
    const container = document.getElementById('cyContainer');
    if (!container) return;

    // Build elements
    allElements = [];

    // Nodes
    if (data.nodes) {
      data.nodes.forEach(node => {
        allElements.push({
          group: 'nodes',
          data: {
            id: node.id,
            label: node.label,
            node_type: node.node_type,
            status_code: node.status_code,
            ...node.metadata,
          },
        });
      });
    }

    // Edges
    if (data.edges) {
      data.edges.forEach((edge, i) => {
        allElements.push({
          group: 'edges',
          data: {
            id: `e${i}`,
            source: edge.source,
            target: edge.target,
            edge_type: edge.edge_type,
            label: edge.label || '',
          },
        });
      });
    }

    // Create Cytoscape instance
    cy = cytoscape({
      container: container,
      elements: allElements,
      style: [
        {
          selector: 'node',
          style: {
            'label': 'data(label)',
            'font-size': '9px',
            'font-family': "'Inter', sans-serif",
            'color': '#e4e4ed',
            'text-valign': 'bottom',
            'text-margin-y': 5,
            'text-max-width': '100px',
            'text-wrap': 'ellipsis',
            'width': 26,
            'height': 26,
            'border-width': 2,
            'border-color': '#2a2a4a',
            'text-outline-width': 2,
            'text-outline-color': '#0a0a1a',
          },
        },
        {
          selector: 'node[node_type="page"]',
          style: {
            'background-color': NODE_COLORS.page,
            'shape': NODE_SHAPES.page,
          },
        },
        {
          selector: 'node[node_type="fuzzed"]',
          style: {
            'background-color': NODE_COLORS.fuzzed,
            'shape': NODE_SHAPES.fuzzed,
          },
        },
        {
          selector: 'node[node_type="form"]',
          style: {
            'background-color': NODE_COLORS.form,
            'shape': NODE_SHAPES.form,
            'width': 22,
            'height': 22,
          },
        },
        {
          selector: 'node[node_type="external"]',
          style: {
            'background-color': NODE_COLORS.external,
            'shape': NODE_SHAPES.external,
          },
        },
        {
          selector: 'edge',
          style: {
            'width': 1.5,
            'line-color': '#3a3a6a',
            'target-arrow-color': '#3a3a6a',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'arrow-scale': 0.7,
            'opacity': 0.7,
          },
        },
        {
          selector: 'edge[edge_type="form_submit"]',
          style: {
            'line-color': '#7c3aed',
            'target-arrow-color': '#7c3aed',
            'line-style': 'dashed',
          },
        },
        {
          selector: ':selected',
          style: {
            'border-color': '#00d4ff',
            'border-width': 3,
            'box-shadow': '0 0 12px #00d4ff',
          },
        },
      ],
      layout: buildLayoutOptions('cose'),
      minZoom: 0.2,
      maxZoom: 4,
      textureOnViewport: true,
      pixelRatio: 1,
    });

    setupTooltip();
    setupFilters();
    setupLayoutSwitcher();
    setupFitButton();
    setupTreeView(data.tree);
  }

  /** Tooltip on node hover */
  function setupTooltip() {
    const tooltip = document.getElementById('graphTooltip');
    if (!tooltip || !cy) return;

    cy.on('mouseover', 'node', (e) => {
      const node = e.target;
      const d = node.data();
      let html = `<strong>${d.label}</strong>`;
      html += `<div>Tipo: ${d.node_type}</div>`;
      if (d.status_code) html += `<div>Estado: ${d.status_code}</div>`;
      if (d.title) html += `<div>Título: ${d.title}</div>`;
      if (d.content_length) html += `<div>Tamaño: ${(d.content_length / 1024).toFixed(1)} KB</div>`;
      if (d.depth !== undefined) html += `<div>Profundidad: ${d.depth}</div>`;
      if (d.form_type) html += `<div>Tipo Form: ${d.form_type}</div>`;
      if (d.has_csrf !== undefined) html += `<div>CSRF: ${d.has_csrf ? '✅' : '❌'}</div>`;
      if (d.fields !== undefined) html += `<div>Campos: ${d.fields}</div>`;

      tooltip.innerHTML = html;
      tooltip.classList.remove('hidden');
    });

    cy.on('mousemove', 'node', (e) => {
      const pos = e.originalEvent;
      tooltip.style.left = (pos.clientX + 12) + 'px';
      tooltip.style.top = (pos.clientY + 12) + 'px';
    });

    cy.on('mouseout', 'node', () => {
      tooltip.classList.add('hidden');
    });
  }

  /** Filter buttons. Uses .onclick (single handler) so repeated
   *  Graph.init() calls don't stack listeners. */
  function setupFilters() {
    document.querySelectorAll('.filter-btn').forEach(btn => {
      btn.onclick = () => {
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        const filter = btn.dataset.filter;
        if (!cy) return;

        if (filter === 'all') {
          cy.elements().show();
        } else {
          cy.nodes().forEach(node => {
            if (node.data('node_type') === filter) {
              node.show();
              node.connectedEdges().show();
            } else {
              node.hide();
            }
          });
        }
      };
    });
  }

  /** Layout switcher */
  function setupLayoutSwitcher() {
    const select = document.getElementById('graphLayout');
    if (!select || !cy) return;

    select.onchange = () => {
      cy.layout(buildLayoutOptions(select.value)).run();
    };
  }

  /** Layout config per-algorithm. CoSE uses the original force-directed
   *  organization; on very large graphs we still cap iterations so the
   *  browser doesn't lock up, but the visual layout is the original one.
   */
  function buildLayoutOptions(name) {
    const nodeCount = cy ? cy.nodes().length : 0;
    const heavy = nodeCount > 150;
    const base = { name, padding: 40 };

    if (name === 'cose') {
      return {
        ...base,
        animate: true,
        animationDuration: 500,
        nodeRepulsion: () => 8000,
        ...(heavy ? { numIter: 800 } : {}),
      };
    }
    if (name === 'breadthfirst') {
      return { ...base, directed: true, spacingFactor: 1.2, animate: true, animationDuration: 400 };
    }
    return { ...base, animate: true, animationDuration: 400 };
  }

  /** Fit button */
  function setupFitButton() {
    const btn = document.getElementById('btnFitGraph');
    if (!btn || !cy) return;

    btn.onclick = () => {
      cy.fit(undefined, 40);
      cy.animate({ zoom: cy.zoom(), center: { eles: cy.elements() } }, { duration: 300 });
    };
  }

  /** Tree view */
  function setupTreeView(tree) {
    const btn = document.getElementById('btnToggleTree');
    const container = document.getElementById('treeContainer');
    const output = document.getElementById('treeOutput');

    if (!btn || !container || !output) return;

    // Populate immediately so the content is ready before the first click.
    output.textContent = tree && tree.name
      ? renderTree(tree, '', true)
      : '(sin datos — realiza un escaneo primero)';

    btn.onclick = () => {
      // Re-populate on each open in case results were reloaded meanwhile.
      output.textContent = tree && tree.name
        ? renderTree(tree, '', true)
        : '(sin datos — realiza un escaneo primero)';
      container.classList.toggle('hidden');
      btn.textContent = container.classList.contains('hidden')
        ? 'Mostrar Árbol de Rutas'
        : 'Ocultar Árbol de Rutas';
    };
  }

  /** Render tree as ASCII */
  function renderTree(node, prefix, isLast) {
    const connector = isLast ? '└── ' : '├── ';
    const statusTag = node.status ? ` [${node.status}]` : '';
    const typeTag = node.type && node.type !== 'directory' ? ` (${node.type})` : '';
    let result = prefix + connector + node.name + statusTag + typeTag + '\n';

    const childPrefix = prefix + (isLast ? '    ' : '│   ');
    if (node.children) {
      node.children.forEach((child, i) => {
        result += renderTree(child, childPrefix, i === node.children.length - 1);
      });
    }

    return result;
  }

  return { init };
})();

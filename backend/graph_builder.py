"""Graph / tree builder for scan results."""
from __future__ import annotations

from urllib.parse import urlparse

from .models import (
    EdgeType,
    FormInfo,
    FuzzResult,
    GraphEdge,
    GraphNode,
    NodeType,
    PageResult,
)


def _node_id(url: str) -> str:
    """Deterministic short ID for a URL."""
    return url


def _is_external(url: str, base_domain: str) -> bool:
    netloc = urlparse(url).netloc
    return bool(netloc) and netloc != base_domain


def _resolve_target(url: str, base_domain: str) -> tuple[str, str, NodeType]:
    """Return (node_id, label, node_type) for a target URL.

    External URLs collapse to a single node per domain (id=``ext::<domain>``)
    to keep the graph readable when a site links to many external resources.
    """
    parsed = urlparse(url)
    if parsed.netloc and parsed.netloc != base_domain:
        domain = parsed.netloc
        return f"ext::{domain}", domain, NodeType.EXTERNAL
    return url, parsed.path or "/", NodeType.PAGE


def build_graph(
    pages: list[PageResult],
    fuzz_results: list[FuzzResult],
    forms: list[FormInfo],
    page_links: dict[str, list[str]],
    base_domain: str,
) -> tuple[list[GraphNode], list[GraphEdge]]:
    """Build graph nodes and edges from scan data.

    *page_links* maps page URL → list of link URLs found on that page.
    Duplicate (source, target, type) edges are collapsed. External targets
    are grouped by domain into a single node.
    """
    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []
    seen_edges: set[tuple[str, str, str]] = set()

    def add_edge(source: str, target: str, edge_type: EdgeType, label: str | None = None) -> None:
        key = (source, target, edge_type.value)
        if key in seen_edges or source == target:
            return
        seen_edges.add(key)
        edges.append(GraphEdge(source=source, target=target, edge_type=edge_type, label=label))

    def ensure_external_node(node_id: str, label: str) -> None:
        if node_id not in nodes:
            nodes[node_id] = GraphNode(
                id=node_id,
                label=label,
                node_type=NodeType.EXTERNAL,
                metadata={"domain": label},
            )

    # 1. Pages (visited by the spider — always internal or explicitly-visited external)
    for p in pages:
        if _is_external(p.url, base_domain):
            # Externals collapsed to a per-domain node
            node_id, label, _ = _resolve_target(p.url, base_domain)
            ensure_external_node(node_id, label)
            continue
        nid = _node_id(p.url)
        parsed = urlparse(p.url)
        nodes[nid] = GraphNode(
            id=nid,
            label=parsed.path or "/",
            node_type=NodeType.PAGE,
            status_code=p.status_code,
            metadata={
                "title": p.title or "",
                "content_length": p.content_length,
                "depth": p.depth,
                "links_found": p.links_found,
                "forms_found": p.forms_found,
            },
        )

    # 2. Links → edges (with dedup; externals collapsed per domain)
    for source_url, targets in page_links.items():
        source_id = _node_id(source_url)
        for target_url in targets:
            tid, label, ttype = _resolve_target(target_url, base_domain)
            if tid not in nodes:
                if ttype == NodeType.EXTERNAL:
                    ensure_external_node(tid, label)
                else:
                    nodes[tid] = GraphNode(
                        id=tid,
                        label=label,
                        node_type=NodeType.PAGE,
                        metadata={},
                    )
            add_edge(source_id, tid, EdgeType.LINK)

    # 3. Fuzzed paths
    for fr in fuzz_results:
        nid = _node_id(fr.url)
        if nid not in nodes:
            nodes[nid] = GraphNode(
                id=nid,
                label=fr.path,
                node_type=NodeType.FUZZED,
                status_code=fr.status_code,
                metadata={
                    "content_length": fr.content_length,
                    "redirect_url": fr.redirect_url or "",
                },
            )

    # 4. Forms
    for fi in forms:
        form_id = f"form::{fi.page_url}::{fi.action}::{fi.method}"
        if form_id not in nodes:
            nodes[form_id] = GraphNode(
                id=form_id,
                label=f"Form ({fi.method.upper()})",
                node_type=NodeType.FORM,
                metadata={
                    "action": fi.action or "",
                    "method": fi.method,
                    "form_type": fi.form_type.value,
                    "fields": len(fi.fields),
                    "has_csrf": fi.has_csrf_token,
                },
            )
        # Edge from page to form
        add_edge(_node_id(fi.page_url), form_id, EdgeType.FORM_SUBMIT, fi.method.upper())
        # Edge from form to action target (if different from page)
        if fi.action and fi.action != fi.page_url:
            action_id, action_label, action_type = _resolve_target(fi.action, base_domain)
            if action_id not in nodes:
                if action_type == NodeType.EXTERNAL:
                    ensure_external_node(action_id, action_label)
                else:
                    nodes[action_id] = GraphNode(
                        id=action_id,
                        label=action_label,
                        node_type=NodeType.PAGE,
                        metadata={},
                    )
            add_edge(form_id, action_id, EdgeType.FORM_SUBMIT)

    return list(nodes.values()), edges


def build_path_tree(pages: list[PageResult], fuzz_results: list[FuzzResult]) -> dict:
    """Build a hierarchical tree of URL paths.

    Returns a nested dict like:
    {
      "name": "/",
      "children": [
        { "name": "admin", "children": [...], "url": "...", "status": 200 },
        ...
      ]
    }
    """
    tree: dict = {"name": "/", "children": [], "url": None, "status": None, "type": "directory"}

    all_paths: list[tuple[str, int | None, str]] = []
    for p in pages:
        parsed = urlparse(p.url)
        all_paths.append((parsed.path or "/", p.status_code, "page"))
    for fr in fuzz_results:
        all_paths.append((fr.path, fr.status_code, "fuzzed"))

    for path, status, ntype in all_paths:
        segments = [s for s in path.split("/") if s]
        current = tree
        for seg in segments:
            found = None
            for child in current["children"]:
                if child["name"] == seg:
                    found = child
                    break
            if found is None:
                found = {"name": seg, "children": [], "url": None, "status": None, "type": "directory"}
                current["children"].append(found)
            current = found
        current["url"] = path
        current["status"] = status
        current["type"] = ntype

    return tree

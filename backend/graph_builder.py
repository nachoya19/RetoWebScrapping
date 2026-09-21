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


def build_graph(
    pages: list[PageResult],
    fuzz_results: list[FuzzResult],
    forms: list[FormInfo],
    page_links: dict[str, list[str]],
    base_domain: str,
) -> tuple[list[GraphNode], list[GraphEdge]]:
    """Build graph nodes and edges from scan data.

    *page_links* maps page URL → list of link URLs found on that page.
    """
    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []

    # 1. Pages
    for p in pages:
        nid = _node_id(p.url)
        parsed = urlparse(p.url)
        is_external = parsed.netloc and parsed.netloc != base_domain
        ntype = NodeType.EXTERNAL if is_external else NodeType.PAGE
        nodes[nid] = GraphNode(
            id=nid,
            label=parsed.path or "/",
            node_type=ntype,
            status_code=p.status_code,
            metadata={
                "title": p.title or "",
                "content_length": p.content_length,
                "depth": p.depth,
                "links_found": p.links_found,
                "forms_found": p.forms_found,
            },
        )

    # 2. Links → edges
    for source_url, targets in page_links.items():
        for target_url in targets:
            # Ensure target node exists
            tid = _node_id(target_url)
            if tid not in nodes:
                parsed = urlparse(target_url)
                is_ext = parsed.netloc and parsed.netloc != base_domain
                nodes[tid] = GraphNode(
                    id=tid,
                    label=parsed.path or target_url,
                    node_type=NodeType.EXTERNAL if is_ext else NodeType.PAGE,
                    metadata={},
                )
            edges.append(
                GraphEdge(source=_node_id(source_url), target=tid, edge_type=EdgeType.LINK)
            )

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
        edges.append(
            GraphEdge(
                source=_node_id(fi.page_url),
                target=form_id,
                edge_type=EdgeType.FORM_SUBMIT,
                label=fi.method.upper(),
            )
        )
        # Edge from form to action target (if different from page)
        if fi.action and fi.action != fi.page_url:
            action_id = _node_id(fi.action)
            if action_id not in nodes:
                parsed = urlparse(fi.action)
                is_ext = parsed.netloc and parsed.netloc != base_domain
                nodes[action_id] = GraphNode(
                    id=action_id,
                    label=parsed.path or fi.action,
                    node_type=NodeType.EXTERNAL if is_ext else NodeType.PAGE,
                    metadata={},
                )
            edges.append(
                GraphEdge(source=form_id, target=action_id, edge_type=EdgeType.FORM_SUBMIT)
            )

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

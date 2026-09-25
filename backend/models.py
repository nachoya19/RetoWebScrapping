"""Pydantic models for WebMapper."""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


# ──────────────────────────────────────────────
# Scan configuration (input)
# ──────────────────────────────────────────────
class ScanConfig(BaseModel):
    """Parameters supplied by the user to start a scan."""

    url: str = Field(..., description="Target URL (including scheme)")
    depth: int = Field(default=1, ge=0, le=3, description="Spider depth 0-3")
    max_pages: int = Field(default=50, ge=1, le=500, description="Max pages to visit")
    enable_fuzzing: bool = Field(default=False, description="Enable content fuzzing")
    include_subdomains: bool = Field(default=False, description="Follow subdomains")
    request_delay: float = Field(default=1.0, ge=1.0, description="Delay between requests in seconds (min 1s per spec)")
    fuzz_extensions: list[str] = Field(
        default_factory=lambda: [".php", ".html", ".js", ".txt", ".bak", ".old", ".conf"],
        description="Extensions to try during fuzzing",
    )
    fuzz_concurrency: int = Field(default=5, ge=1, le=20, description="Concurrent fuzzing requests")
    authorized: bool = Field(default=False, description="User confirmed authorization")


# ──────────────────────────────────────────────
# Node / Edge types
# ──────────────────────────────────────────────
class NodeType(str, Enum):
    PAGE = "page"
    FUZZED = "fuzzed"
    FORM = "form"
    EXTERNAL = "external"


class EdgeType(str, Enum):
    LINK = "link"
    RESOURCE = "resource"
    FORM_SUBMIT = "form_submit"


# ──────────────────────────────────────────────
# Form classification
# ──────────────────────────────────────────────
class FormType(str, Enum):
    LOGIN = "login"
    SEARCH = "search"
    UPLOAD = "upload"
    OTHER = "other"


# ──────────────────────────────────────────────
# Result models
# ──────────────────────────────────────────────
class FormField(BaseModel):
    """A single field inside a form."""

    name: Optional[str] = None
    type: str = "text"
    value: Optional[str] = None
    placeholder: Optional[str] = None
    required: bool = False
    is_hidden: bool = False


class FormInfo(BaseModel):
    """A form found on a page."""

    page_url: str
    action: Optional[str] = None
    method: str = "get"
    enctype: Optional[str] = None
    fields: list[FormField] = Field(default_factory=list)
    has_csrf_token: bool = False
    csrf_field_name: Optional[str] = None
    form_type: FormType = FormType.OTHER


class PageResult(BaseModel):
    """Result for a single visited page."""

    url: str
    status_code: int = 0
    content_length: int = 0
    title: Optional[str] = None
    depth: int = 0
    links_found: int = 0
    forms_found: int = 0
    error: Optional[str] = None


class FuzzResult(BaseModel):
    """Result for a single fuzzed path."""

    url: str
    path: str
    status_code: int
    content_length: int = 0
    redirect_url: Optional[str] = None


# ──────────────────────────────────────────────
# Graph structures
# ──────────────────────────────────────────────
class GraphNode(BaseModel):
    id: str
    label: str
    node_type: NodeType
    status_code: Optional[int] = None
    metadata: dict = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source: str
    target: str
    edge_type: EdgeType
    label: Optional[str] = None


# ──────────────────────────────────────────────
# Aggregated scan results
# ──────────────────────────────────────────────
class ScanResults(BaseModel):
    """Full results returned after a scan completes."""

    config: ScanConfig
    pages: list[PageResult] = Field(default_factory=list)
    forms: list[FormInfo] = Field(default_factory=list)
    fuzz_results: list[FuzzResult] = Field(default_factory=list)
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    tree: dict = Field(default_factory=dict)

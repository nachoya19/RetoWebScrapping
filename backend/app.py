"""FastAPI application — endpoints, SSE, and static file serving."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI, File, UploadFile, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles

from .exporter import export_csv_zip, export_html, export_json
from .fuzzer import Fuzzer
from .graph_builder import build_graph, build_path_tree
from .models import ScanConfig, ScanResults
from .spider import Spider

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webmapper")

# ── Paths ───────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
WORDLIST_DIR = os.path.join(BASE_DIR, "wordlists")
DEFAULT_WORDLIST = os.path.join(WORDLIST_DIR, "common.txt")

# ── App ─────────────────────────────────────
app = FastAPI(title="WebMapper", version="1.0.0")

# Mount static files
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

# ── Global state ────────────────────────────
_scan_state: dict[str, Any] = {
    "running": False,
    "progress_queue": None,  # asyncio.Queue
    "spider": None,
    "fuzzer": None,
    "results": None,
    "custom_wordlist": None,
}


# ── Serve frontend ──────────────────────────
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


# ── SSE progress stream ────────────────────
@app.get("/api/scan/progress")
async def scan_progress(request: Request):
    async def event_stream():
        q: asyncio.Queue = _scan_state["progress_queue"]
        if q is None:
            yield "data: {\"type\":\"error\",\"message\":\"No scan running\"}\n\n"
            return
        while True:
            if await request.is_disconnected():
                break
            try:
                msg = await asyncio.wait_for(q.get(), timeout=1.0)
                yield f"data: {json.dumps(msg)}\n\n"
                if msg.get("type") == "scan" and msg.get("status") in ("finished", "error"):
                    break
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── Start scan ──────────────────────────────
@app.post("/api/scan/start")
async def start_scan(config: ScanConfig):
    if _scan_state["running"]:
        return JSONResponse({"error": "A scan is already running"}, status_code=409)

    if not config.authorized:
        return JSONResponse({"error": "Authorization confirmation required"}, status_code=403)

    # Validate URL
    parsed = urlparse(config.url)
    if not parsed.scheme or not parsed.netloc:
        return JSONResponse({"error": "Invalid URL — include scheme (http/https)"}, status_code=400)

    _scan_state["running"] = True
    _scan_state["progress_queue"] = asyncio.Queue()
    _scan_state["results"] = None

    asyncio.create_task(_run_scan(config))
    return {"status": "started"}


async def _run_scan(config: ScanConfig):
    """Background task that runs spider + optional fuzzer."""
    q: asyncio.Queue = _scan_state["progress_queue"]

    def emit(data: dict):
        try:
            q.put_nowait(data)
        except Exception:
            pass

    try:
        emit({"type": "scan", "status": "starting", "phase": "spider"})

        # ── Spider ──
        spider = Spider(
            start_url=config.url,
            depth=config.depth,
            max_pages=config.max_pages,
            include_subdomains=config.include_subdomains,
            request_delay=config.request_delay,
            on_progress=emit,
        )
        _scan_state["spider"] = spider
        await spider.run()

        parsed = urlparse(config.url)
        base_domain = parsed.netloc

        pages = spider.pages
        forms = spider.forms
        page_links = spider.page_links

        # ── Fuzzer (optional) ──
        fuzz_results = []
        if config.enable_fuzzing:
            emit({"type": "scan", "status": "starting", "phase": "fuzzer"})
            wordlist = _scan_state.get("custom_wordlist") or DEFAULT_WORDLIST
            fuzzer = Fuzzer(
                base_url=config.url,
                wordlist_path=wordlist,
                extensions=config.fuzz_extensions,
                concurrency=config.fuzz_concurrency,
                request_delay=config.request_delay,
                on_progress=emit,
            )
            _scan_state["fuzzer"] = fuzzer
            await fuzzer.run()
            fuzz_results = fuzzer.results

        # ── Build graph ──
        emit({"type": "scan", "status": "building_graph"})
        nodes, edges = build_graph(pages, fuzz_results, forms, page_links, base_domain)
        tree = build_path_tree(pages, fuzz_results)

        results = ScanResults(
            config=config,
            pages=pages,
            forms=forms,
            fuzz_results=fuzz_results,
            nodes=nodes,
            edges=edges,
            tree=tree,
        )
        _scan_state["results"] = results

        emit({
            "type": "scan",
            "status": "finished",
            "pages_count": len(pages),
            "forms_count": len(forms),
            "fuzz_count": len(fuzz_results),
        })

    except Exception as exc:
        logger.exception("Scan failed")
        emit({"type": "scan", "status": "error", "message": str(exc)})
    finally:
        _scan_state["running"] = False
        _scan_state["spider"] = None
        _scan_state["fuzzer"] = None


# ── Stop scan ───────────────────────────────
@app.post("/api/scan/stop")
async def stop_scan():
    if not _scan_state["running"]:
        return JSONResponse({"error": "No scan running"}, status_code=404)

    if _scan_state["spider"]:
        _scan_state["spider"].stop()
    if _scan_state["fuzzer"]:
        _scan_state["fuzzer"].stop()

    return {"status": "stopping"}


# ── Results ─────────────────────────────────
@app.get("/api/results")
async def get_results():
    results: ScanResults | None = _scan_state["results"]
    if results is None:
        return JSONResponse({"error": "No results available"}, status_code=404)
    return json.loads(results.model_dump_json())


# ── Export ──────────────────────────────────
@app.get("/api/export/{fmt}")
async def export_results(fmt: str):
    results: ScanResults | None = _scan_state["results"]
    if results is None:
        return JSONResponse({"error": "No results available"}, status_code=404)

    if fmt == "json":
        return Response(
            content=export_json(results),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=webmapper_report.json"},
        )
    elif fmt == "csv":
        return Response(
            content=export_csv_zip(results),
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=webmapper_report.zip"},
        )
    elif fmt == "html":
        return Response(
            content=export_html(results),
            media_type="text/html",
            headers={"Content-Disposition": "attachment; filename=webmapper_report.html"},
        )
    else:
        return JSONResponse({"error": "Format must be json, csv, or html"}, status_code=400)


# ── Upload wordlist ─────────────────────────
@app.post("/api/wordlist")
async def upload_wordlist(file: UploadFile = File(...)):
    content = await file.read()
    dest = os.path.join(WORDLIST_DIR, "custom.txt")
    with open(dest, "wb") as f:
        f.write(content)
    _scan_state["custom_wordlist"] = dest
    lines = content.decode("utf-8", errors="ignore").strip().split("\n")
    return {"status": "ok", "words": len(lines), "path": dest}


# ── Scan status ─────────────────────────────
@app.get("/api/scan/status")
async def scan_status():
    return {
        "running": _scan_state["running"],
        "has_results": _scan_state["results"] is not None,
    }

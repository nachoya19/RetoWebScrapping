"""Content fuzzer — discovers unlisted paths via dictionary attack."""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Callable

import httpx

from .models import FuzzResult

logger = logging.getLogger("webmapper.fuzzer")

USER_AGENT = "WebMapper/1.0 (Educational Security Tool)"

DEFAULT_WORDLIST = os.path.join(os.path.dirname(os.path.dirname(__file__)), "wordlists", "common.txt")


class Fuzzer:
    """Async content fuzzer with concurrency and rate-limit controls."""

    def __init__(
        self,
        base_url: str,
        wordlist_path: str | None = None,
        extensions: list[str] | None = None,
        concurrency: int = 5,
        request_delay: float = 0.5,
        on_progress: Callable[[dict], None] | None = None,
    ):
        # Ensure base URL ends without a trailing slash
        self.base_url = base_url.rstrip("/")
        self.wordlist_path = wordlist_path or DEFAULT_WORDLIST
        self.extensions = extensions or []
        self.concurrency = max(1, concurrency)
        self.request_delay = max(0.2, request_delay)
        self.on_progress = on_progress

        self.results: list[FuzzResult] = []
        self._stop = asyncio.Event()
        self._semaphore = asyncio.Semaphore(self.concurrency)
        self._total = 0
        self._done = 0

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        """Load wordlist and fuzz all paths."""
        words = self._load_wordlist()
        if not words:
            logger.warning("No words loaded from wordlist")
            return

        # Build path list: word + word.ext
        paths: list[str] = []
        for word in words:
            paths.append(word)
            for ext in self.extensions:
                ext = ext if ext.startswith(".") else f".{ext}"
                paths.append(f"{word}{ext}")

        self._total = len(paths)
        self._done = 0

        self._emit({
            "type": "fuzzer",
            "status": "starting",
            "total_paths": self._total,
        })

        async with httpx.AsyncClient(
            follow_redirects=False,
            timeout=10.0,
            headers={"User-Agent": USER_AGENT},
            verify=False,
        ) as client:
            tasks = []
            for path in paths:
                if self._stop.is_set():
                    break
                tasks.append(self._fuzz_path(client, path))

            await asyncio.gather(*tasks)

        self._emit({
            "type": "fuzzer",
            "status": "finished",
            "total_paths": self._total,
            "found": len(self.results),
        })

    async def _fuzz_path(self, client: httpx.AsyncClient, path: str) -> None:
        if self._stop.is_set():
            return

        async with self._semaphore:
            if self._stop.is_set():
                return

            url = f"{self.base_url}/{path.lstrip('/')}"
            try:
                resp = await client.get(url)
                self._done += 1

                # Only record "interesting" responses (not 404)
                if resp.status_code != 404:
                    redirect_url = None
                    if resp.status_code in (301, 302, 303, 307, 308):
                        redirect_url = resp.headers.get("location", "")

                    result = FuzzResult(
                        url=url,
                        path=path,
                        status_code=resp.status_code,
                        content_length=len(resp.content),
                        redirect_url=redirect_url,
                    )
                    self.results.append(result)

                    self._emit({
                        "type": "fuzzer",
                        "status": "found",
                        "path": path,
                        "url": url,
                        "status_code": resp.status_code,
                        "content_length": len(resp.content),
                        "done": self._done,
                        "total": self._total,
                    })
                else:
                    if self._done % 20 == 0:
                        self._emit({
                            "type": "fuzzer",
                            "status": "progress",
                            "done": self._done,
                            "total": self._total,
                        })

            except Exception as exc:
                self._done += 1
                logger.debug("Fuzz error for %s: %s", path, exc)

            await asyncio.sleep(self.request_delay)

    def _load_wordlist(self) -> list[str]:
        """Load words from the wordlist file."""
        try:
            with open(self.wordlist_path, "r", encoding="utf-8") as f:
                words = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            logger.info("Loaded %d words from %s", len(words), self.wordlist_path)
            return words
        except FileNotFoundError:
            logger.error("Wordlist not found: %s", self.wordlist_path)
            return []

    def _emit(self, data: dict) -> None:
        if self.on_progress:
            self.on_progress(data)

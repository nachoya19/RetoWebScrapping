"""Spider engine — crawls a website following internal links."""
from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator, Callable
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup, Tag

from .form_extractor import extract_forms
from .models import FormInfo, PageResult

logger = logging.getLogger("webmapper.spider")

USER_AGENT = "WebMapper/1.0 (Educational Security Tool)"


class Spider:
    """Async web spider with configurable depth, domain filtering and rate limiting."""

    def __init__(
        self,
        start_url: str,
        depth: int = 1,
        max_pages: int = 50,
        include_subdomains: bool = False,
        request_delay: float = 1.0,
        on_progress: Callable[[dict], None] | None = None,
    ):
        parsed = urlparse(start_url)
        self.start_url = start_url
        self.base_scheme = parsed.scheme or "https"
        self.base_domain = parsed.netloc
        self.depth = depth
        self.max_pages = max_pages
        self.include_subdomains = include_subdomains
        self.request_delay = max(request_delay, 1.0)
        self.on_progress = on_progress

        # State
        self.visited: set[str] = set()
        self.pages: list[PageResult] = []
        self.forms: list[FormInfo] = []
        self.page_links: dict[str, list[str]] = {}  # url -> [linked urls]
        self._stop = asyncio.Event()
        self._robots: RobotFileParser | None = None

    # ── public API ──────────────────────────────
    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        """Start crawling."""
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=15.0,
            headers={"User-Agent": USER_AGENT},
            verify=False,
        ) as client:
            self._client = client
            await self._load_robots()
            await self._crawl(self.start_url, current_depth=0)

    # ── robots.txt ──────────────────────────────
    async def _load_robots(self) -> None:
        robots_url = f"{self.base_scheme}://{self.base_domain}/robots.txt"
        try:
            resp = await self._client.get(robots_url, timeout=10)
            if resp.status_code == 200:
                rp = RobotFileParser()
                rp.parse(resp.text.splitlines())
                self._robots = rp
                logger.info("robots.txt loaded from %s", robots_url)
        except Exception:
            logger.debug("Could not fetch robots.txt")

    def _can_fetch(self, url: str) -> bool:
        if self._robots is None:
            return True
        return self._robots.can_fetch(USER_AGENT, url)

    # ── domain check ────────────────────────────
    def _is_same_domain(self, url: str) -> bool:
        parsed = urlparse(url)
        netloc = parsed.netloc
        if not netloc:
            return True
        if netloc == self.base_domain:
            return True
        if self.include_subdomains and netloc.endswith("." + self.base_domain):
            return True
        return False

    # ── normalize ───────────────────────────────
    @staticmethod
    def _normalize(url: str) -> str:
        parsed = urlparse(url)
        # Remove fragment
        return parsed._replace(fragment="").geturl()

    # ── crawl ───────────────────────────────────
    async def _crawl(self, url: str, current_depth: int) -> None:
        if self._stop.is_set():
            return
        if len(self.visited) >= self.max_pages:
            return

        url = self._normalize(url)
        if url in self.visited:
            return
        if not self._can_fetch(url):
            logger.info("Blocked by robots.txt: %s", url)
            return

        self.visited.add(url)

        # Emit progress
        self._emit({
            "type": "spider",
            "status": "visiting",
            "url": url,
            "depth": current_depth,
            "visited": len(self.visited),
            "max_pages": self.max_pages,
        })

        page_result = PageResult(url=url, depth=current_depth)

        try:
            resp = await self._client.get(url)
            page_result.status_code = resp.status_code
            page_result.content_length = len(resp.content)

            content_type = resp.headers.get("content-type", "")
            if "text/html" not in content_type:
                self.pages.append(page_result)
                return

            html = resp.text
            soup = BeautifulSoup(html, "lxml")

            # Title
            title_tag = soup.find("title")
            if title_tag:
                page_result.title = title_tag.get_text(strip=True)

            # Extract links
            links: list[str] = []
            for a_tag in soup.find_all("a", href=True):
                if not isinstance(a_tag, Tag):
                    continue
                href = a_tag.get("href", "")
                if isinstance(href, list):
                    href = href[0] if href else ""
                if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
                    continue
                full_url = self._normalize(urljoin(url, href))
                links.append(full_url)

            page_result.links_found = len(links)
            self.page_links[url] = links

            # Extract forms
            page_forms = extract_forms(html, url)
            page_result.forms_found = len(page_forms)
            self.forms.extend(page_forms)

            self.pages.append(page_result)

            # Follow internal links at next depth
            if current_depth < self.depth:
                for link in links:
                    if self._stop.is_set():
                        break
                    if len(self.visited) >= self.max_pages:
                        break
                    if self._is_same_domain(link) and link not in self.visited:
                        await asyncio.sleep(self.request_delay)
                        await self._crawl(link, current_depth + 1)

        except httpx.TimeoutException:
            page_result.error = "Timeout"
            self.pages.append(page_result)
        except Exception as exc:
            page_result.error = str(exc)
            self.pages.append(page_result)

    # ── progress helper ─────────────────────────
    def _emit(self, data: dict) -> None:
        if self.on_progress:
            self.on_progress(data)

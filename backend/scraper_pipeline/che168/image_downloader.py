"""Async image downloader for Che168 galleries."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

import aiohttp


def _ext_from_content_type(content_type: str) -> str:
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct == "image/webp":
        return ".webp"
    if ct in ("image/jpeg", "image/jpg"):
        return ".jpg"
    if ct == "image/png":
        return ".png"
    return ""


def _ext_from_url(url: str) -> str:
    p = urlsplit(url or "")
    path = (p.path or "").lower()
    if path.endswith(".webp"):
        return ".webp"
    if path.endswith(".jpeg") or path.endswith(".jpg"):
        return ".jpg"
    if path.endswith(".png"):
        return ".png"
    return ".img"


class AsyncImageDownloader:
    def __init__(self, config: dict, log: logging.Logger):
        self.log = log
        ch = config.get("che168", {}) or {}
        cfg = ch.get("image_download") if isinstance(ch.get("image_download"), dict) else {}
        self.enabled = bool(cfg.get("enabled", False))
        self.root = Path(str(cfg.get("root_dir") or "var/che168_images"))
        self.max_parallel = max(1, int(cfg.get("max_parallel", 4) or 4))
        self.max_attempts = max(1, int(cfg.get("max_attempts", 3) or 3))
        self.timeout_total = float(cfg.get("timeout_total_sec", 25) or 25)
        self.retry_backoff_sec = float(cfg.get("retry_backoff_sec", 0.8) or 0.8)
        self.min_size_bytes = int(cfg.get("min_size_bytes", 256) or 256)
        self._hash_seen: set[str] = set()
        self._sem = asyncio.Semaphore(self.max_parallel)
        self._session: Optional[aiohttp.ClientSession] = None
        self._headers = {
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Referer": str(ch.get("referer", "https://global.che168.com/")),
            "Origin": str(ch.get("origin", "https://global.che168.com")),
        }

    async def __aenter__(self) -> "AsyncImageDownloader":
        if not self.enabled:
            return self
        self.root.mkdir(parents=True, exist_ok=True)
        self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout_total))
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def _fetch_one(self, car_id: str, idx: int, url: str) -> Optional[Dict[str, Any]]:
        if not self.enabled or self._session is None:
            return None
        if not isinstance(url, str) or not url.strip():
            return None
        url = url.strip()
        async with self._sem:
            for attempt in range(1, self.max_attempts + 1):
                try:
                    async with self._session.get(url, headers=self._headers, allow_redirects=True) as resp:
                        if int(resp.status) != 200:
                            if attempt < self.max_attempts and int(resp.status) in (403, 404, 429, 500, 502, 503, 504):
                                await asyncio.sleep(self.retry_backoff_sec * attempt)
                                continue
                            return None
                        body = await resp.read()
                        if len(body) < self.min_size_bytes:
                            return None
                        md5 = hashlib.md5(body).hexdigest()
                        if md5 in self._hash_seen:
                            return {"url": url, "duplicate": True, "md5": md5}
                        self._hash_seen.add(md5)
                        ext = _ext_from_content_type(resp.headers.get("Content-Type", "")) or _ext_from_url(url)
                        car_dir = self.root / car_id
                        car_dir.mkdir(parents=True, exist_ok=True)
                        fn = car_dir / f"{idx:03d}_{md5[:10]}{ext}"
                        fn.write_bytes(body)
                        return {
                            "url": url,
                            "path": str(fn),
                            "bytes": len(body),
                            "md5": md5,
                            "content_type": resp.headers.get("Content-Type", ""),
                        }
                except asyncio.CancelledError:
                    raise
                except Exception:
                    if attempt < self.max_attempts:
                        await asyncio.sleep(self.retry_backoff_sec * attempt)
                        continue
                    return None
        return None

    async def download_many(self, *, car_id: str, urls: List[str]) -> Dict[str, Any]:
        if not self.enabled:
            return {"enabled": False, "assets": [], "downloaded": 0, "attempted": 0}
        clean_urls = [u.strip() for u in urls if isinstance(u, str) and u.strip()]
        if not clean_urls:
            return {"enabled": True, "assets": [], "downloaded": 0, "attempted": 0}
        # Ленивая сессия: позволяет вызывать downloader без явного async-with в воркере.
        close_after = False
        if self._session is None:
            self.root.mkdir(parents=True, exist_ok=True)
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout_total))
            close_after = True
        tasks = [self._fetch_one(car_id, i + 1, u) for i, u in enumerate(clean_urls)]
        done = await asyncio.gather(*tasks, return_exceptions=True)
        assets: List[Dict[str, Any]] = []
        duplicates = 0
        for d in done:
            if isinstance(d, Exception) or not d:
                continue
            if d.get("duplicate"):
                duplicates += 1
                continue
            assets.append(d)
        out = {
            "enabled": True,
            "attempted": len(clean_urls),
            "downloaded": len(assets),
            "duplicates": duplicates,
            "assets": assets,
        }
        if close_after and self._session is not None:
            await self._session.close()
            self._session = None
        return out

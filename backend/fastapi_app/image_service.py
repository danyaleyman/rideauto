"""
Прокси оптимизации изображений: загрузка оригинала → ресайз → WebP → дисковый кэш.

Идентификатор в URL: ``sha256(url.strip().encode('utf-8')).hexdigest()`` (64 hex).
При первом запросе (кэш промах) передайте ``?src=`` с URL-кодированием исходного адреса;
после записи на диск тот же путь отдаётся без ``src``. Опционально исходный URL
дублируется в Redis (``wra:img:src:{digest}``), чтобы не таскать ``src`` в CDN.

Безопасность: только HTTPS (опционально HTTP для внутренних контуров), хосты из allowlist (WRA_IMAGE_ALLOWED_HOSTS).
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import re
from pathlib import Path
from typing import FrozenSet, Literal, Optional
from urllib.parse import urlparse

import httpx

_log = logging.getLogger(__name__)

_SIZE_MAX: dict[str, int] = {"thumb": 300, "medium": 800}
_RE_DIGEST = re.compile(r"^[a-f0-9]{64}$", re.I)

ImageSize = Literal["thumb", "medium"]


class ImageServiceError(Exception):
    pass


class ImageSourceMissingError(ImageServiceError):
    """Нет файла в кэше и не передан src / Redis."""


class ImageDigestMismatchError(ImageServiceError):
    """src не соответствует digest."""


class ImageFetchError(ImageServiceError):
    pass


class ImageNotAllowedError(ImageServiceError):
    """Хост или схема URL не в allowlist."""


def digest_for_url(url: str) -> str:
    return hashlib.sha256(url.strip().encode("utf-8")).hexdigest().lower()


def parse_allowed_hosts(raw: str) -> FrozenSet[str]:
    parts = [p.strip().lower() for p in (raw or "").split(",") if p.strip()]
    return frozenset(parts)


def host_matches_allowed(host: str, allowed: FrozenSet[str]) -> bool:
    """
    Allow exact hostnames plus wildcard rules ``*.example.com`` (also allows apex ``example.com``).
    """
    h = (host or "").lower()
    if not h:
        return False
    if h in allowed:
        return True
    for rule in allowed:
        if rule.startswith("*."):
            base = rule[2:]
            if base and (h == base or h.endswith("." + base)):
                return True
    return False


def normalize_image_id(image_id: str) -> str:
    s = (image_id or "").strip().lower()
    if s.endswith(".webp"):
        s = s[: -len(".webp")]
    return s


def validate_digest(digest: str) -> str:
    d = normalize_image_id(digest)
    if not _RE_DIGEST.match(d):
        raise ImageServiceError("invalid image id (expect 64 hex sha256)")
    return d


def _upstream_body_kind(data: bytes) -> str:
    """Грубая классификация тела ответа для диагностики (без полного парсинга)."""
    if not data:
        return "empty"
    head = data.lstrip()[:800]
    hl = head.lower()
    if hl.startswith(b"<!doctype") or hl.startswith(b"<html") or hl.startswith(b"<head"):
        return "html"
    if head.startswith(b"<") or head.startswith(b"{"):
        return "text_or_markup"
    d = data
    if len(d) >= 3 and d[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if len(d) >= 8 and d[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if len(d) >= 6 and d[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if len(d) >= 12 and d[:4] == b"RIFF" and d[8:12] == b"WEBP":
        return "webp"
    if len(d) >= 2 and d[:2] == b"BM":
        return "bmp"
    if len(d) >= 12 and d[4:8] == b"ftyp":
        return "isobmff"
    if len(data) < 24:
        return "too_short"
    return "unknown"


def _validate_source_url(url: str, allowed: FrozenSet[str]) -> str:
    u = (url or "").strip()
    if not u:
        raise ImageNotAllowedError("empty src")
    p = urlparse(u)
    scheme = (p.scheme or "").lower()
    if scheme not in ("https", "http"):
        raise ImageNotAllowedError("only http(s) URLs")
    host = (p.hostname or "").lower()
    if not host or not host_matches_allowed(host, allowed):
        raise ImageNotAllowedError(f"host not allowed: {host!r}")
    if "/../" in p.path or p.path.startswith("//"):
        raise ImageNotAllowedError("invalid path")
    return u


def _resize_to_webp(
    image_bytes: bytes,
    max_side: int,
    *,
    quality: int = 82,
    content_type: Optional[str] = None,
    digest_prefix: str = "",
) -> bytes:
    from PIL import Image, ImageFile

    ImageFile.LOAD_TRUNCATED_IMAGES = True

    ct = (content_type or "").split(";")[0].strip().lower()
    if ct and any(
        x in ct
        for x in (
            "text/html",
            "application/json",
            "text/json",
            "text/plain",
            "application/xml",
            "text/xml",
        )
    ):
        raise ImageServiceError("upstream Content-Type is not an image")

    kind = _upstream_body_kind(image_bytes)
    if kind in ("html", "text_or_markup"):
        raise ImageServiceError("upstream returned HTML/JSON instead of image (hotlink or error page)")
    if kind == "empty":
        raise ImageServiceError("empty image response from upstream")
    if kind == "too_short":
        raise ImageServiceError("image response too short")

    try:
        im = Image.open(io.BytesIO(image_bytes))
        im.load()
    except Exception as e:
        hint = kind if kind != "unknown" else "unknown_bytes"
        _log.warning(
            "pillow open failed digest=%s kind=%s ct=%r bytes=%s err=%s",
            digest_prefix[:12] if digest_prefix else "?",
            hint,
            ct or None,
            len(image_bytes),
            e,
        )
        if kind == "isobmff":
            raise ImageServiceError(
                "image format not supported (AVIF/HEIC); upstream returned ISO BMFF container"
            ) from e
        raise ImageServiceError("unrecognized or corrupt image (not JPEG/PNG/WebP/GIF)") from e
    if im.mode in ("RGBA", "P"):
        im = im.convert("RGBA")
    else:
        im = im.convert("RGB")
    im.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    save_kw = {"format": "WEBP", "quality": quality, "method": 6}
    if im.mode == "RGBA":
        im.save(out, **save_kw)
    else:
        im.save(out, **save_kw)
    return out.getvalue()


async def _fetch_bytes(
    url: str,
    *,
    timeout_sec: float,
    max_bytes: int,
    headers: Optional[dict[str, str]] = None,
) -> tuple[bytes, Optional[str]]:
    hdrs = {
        "User-Agent": "ProdEncar-ImageProxy/1.0",
        # Без приоритета image/avif: иначе часть CDN отдаёт AVIF, а Pillow без плагина не открывает.
        "Accept": "image/webp,image/apng,image/jpeg,image/png,image/*,*/*;q=0.8",
    }
    if headers:
        hdrs.update(headers)
    try:
        async with httpx.AsyncClient(
            timeout=timeout_sec,
            follow_redirects=True,
            max_redirects=5,
            trust_env=False,
        ) as client:
            async with client.stream("GET", url, headers=hdrs) as r:
                r.raise_for_status()
                ctype = (r.headers.get("content-type") or "").split(";")[0].strip().lower() or None
                total = 0
                chunks: list[bytes] = []
                async for chunk in r.aiter_bytes():
                    total += len(chunk)
                    if total > max_bytes:
                        raise ImageFetchError("image too large")
                    chunks.append(chunk)
                return b"".join(chunks), ctype
    except httpx.HTTPError as e:
        raise ImageFetchError(str(e)) from e


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


async def resolve_source_url(
    digest: str,
    src: Optional[str],
    *,
    redis,
    redis_ttl_sec: int,
) -> str:
    if src and src.strip():
        return src.strip()
    if redis is None:
        raise ImageSourceMissingError("src query required on cold cache")
    key = f"wra:img:src:{digest}"
    cached = await redis.get(key)
    if not cached:
        raise ImageSourceMissingError("src unknown — pass src or warm Redis")
    return str(cached)


async def ensure_cached_webp(
    *,
    digest: str,
    size: ImageSize,
    src: Optional[str],
    cache_dir: Path,
    allowed_hosts: FrozenSet[str],
    fetch_timeout: float,
    max_bytes: int,
    redis=None,
    redis_ttl_sec: int = 604800,
    referer_for_encar: Optional[str] = None,
    referer_for_che168: Optional[str] = None,
) -> Path:
    if size not in _SIZE_MAX:
        raise ImageServiceError("invalid size")
    digest = validate_digest(digest)
    out_path = cache_dir / digest[:2] / f"{digest}_{size}.webp"
    if out_path.is_file():
        return out_path

    url = await resolve_source_url(digest, src, redis=redis, redis_ttl_sec=redis_ttl_sec)
    canon = _validate_source_url(url, allowed_hosts)
    if digest_for_url(canon) != digest:
        raise ImageDigestMismatchError("src does not match image id")

    extra_headers: dict[str, str] = {}
    hn = (urlparse(canon).hostname or "").lower()
    if referer_for_encar and hn.endswith("encar.com"):
        extra_headers["Referer"] = referer_for_encar
    elif referer_for_che168 and (
        hn.endswith(".autoimg.cn")
        or hn == "autoimg.cn"
        or hn.endswith(".che168.com")
        or hn == "che168.com"
        or "byteimg" in hn
        or "bytecdn" in hn
        or "dcarimg" in hn
    ):
        extra_headers["Referer"] = referer_for_che168

    raw, upstream_ct = await _fetch_bytes(
        canon,
        timeout_sec=fetch_timeout,
        max_bytes=max_bytes,
        headers=extra_headers or None,
    )

    def _build() -> bytes:
        return _resize_to_webp(
            raw,
            _SIZE_MAX[size],
            content_type=upstream_ct,
            digest_prefix=digest,
        )

    webp_bytes = await asyncio.to_thread(_build)

    if out_path.is_file():
        return out_path

    await asyncio.to_thread(_atomic_write, out_path, webp_bytes)

    if redis is not None:
        try:
            await redis.set(f"wra:img:src:{digest}", canon, ex=redis_ttl_sec)
        except Exception:
            _log.warning("redis set image src failed for %s", digest[:12])

    return out_path


def public_image_url(base_public_api: str, digest: str, size: ImageSize = "thumb") -> str:
    """
    Публичный URL для HTML/CDN (без src после прогрева кэша).

    base_public_api: например ``https://rideauto.ru/api`` (без завершающего /).
    """
    b = base_public_api.rstrip("/")
    return f"{b}/images/{digest}?size={size}"


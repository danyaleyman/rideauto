from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response

from fastapi_app.config import Settings, get_settings
from fastapi_app.image_service import (
    ImageDigestMismatchError,
    ImageFetchError,
    ImageNotAllowedError,
    ImageServiceError,
    ImageSourceMissingError,
    ensure_cached_webp,
    normalize_image_id,
    parse_allowed_hosts,
)

router = APIRouter(tags=["images"])


@router.get(
    "/images/{image_id}",
    responses={400: {"description": "bad request"}, 404: {"description": "upstream fetch failed"}},
)
async def optimized_image(
    request: Request,
    image_id: str,
    size: Literal["thumb", "medium"] = Query("thumb", description="thumb=300px, medium=800px (max side)"),
    src: Optional[str] = Query(
        None,
        description="Исходный URL изображения (обязателен при холодном кэше, если нет Redis)",
    ),
) -> Response:
    """
    Отдаёт WebP из кэша или строит из оригинала.

    **CDN:** после первого успешного запроса с ``src`` тот же ``/api/images/{sha256}?size=…``
    можно дергать без ``src``; заголовок ``Cache-Control`` длинный для edge-кэша.

    **digest:** ``hashlib.sha256(original_url.strip().encode('utf-8')).hexdigest()``.
    """
    settings: Settings = get_settings()
    digest = normalize_image_id(image_id)
    redis = getattr(request.app.state, "redis", None)
    allowed = parse_allowed_hosts(settings.image_allowed_hosts)
    cache_dir = Path(settings.image_cache_dir)

    try:
        path = await ensure_cached_webp(
            digest=digest,
            size=size,  # type: ignore[arg-type]
            src=src,
            cache_dir=cache_dir,
            allowed_hosts=allowed,
            fetch_timeout=settings.image_fetch_timeout_sec,
            max_bytes=settings.image_max_fetch_bytes,
            redis=redis,
            redis_ttl_sec=settings.image_src_redis_ttl_sec,
            referer_for_encar=(settings.image_encar_referer or "").strip() or None,
        )
    except ImageSourceMissingError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ImageDigestMismatchError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ImageNotAllowedError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ImageServiceError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ImageFetchError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    st = path.stat()
    etag = f'W/"img-{st.st_mtime_ns}-{st.st_size}"'
    cc = settings.image_response_cache_control
    hdrs = {"Cache-Control": cc, "ETag": etag, "Vary": "Accept"}

    inm = (request.headers.get("if-none-match") or "").strip()
    if inm:
        for part in inm.split(","):
            t = part.strip()
            if t == "*" or t == etag:
                return Response(status_code=304, headers=dict(hdrs))

    return FileResponse(path, media_type="image/webp", headers=dict(hdrs))


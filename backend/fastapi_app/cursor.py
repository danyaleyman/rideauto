from __future__ import annotations

import base64
import json
from typing import Optional, Tuple


def encode_offset_cursor(offset: int, limit: int, *, version: int = 1) -> str:
    payload = {"v": version, "o": int(offset), "l": int(limit)}
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_offset_cursor(token: Optional[str]) -> Optional[Tuple[int, int]]:
    if not token or not str(token).strip():
        return None
    pad = "=" * (-len(token) % 4)
    try:
        data = base64.urlsafe_b64decode(str(token).strip() + pad)
        obj = json.loads(data.decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(obj, dict) or int(obj.get("v", 0)) != 1:
        return None
    try:
        offset = int(obj["o"])
        limit = int(obj["l"])
    except (KeyError, TypeError, ValueError):
        return None
    if offset < 0 or limit < 1:
        return None
    return offset, limit

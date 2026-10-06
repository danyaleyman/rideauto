"""SessionBundle — куки/прокси/identity после browser bootstrap."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional


@dataclass
class SessionBundle:
    """Живая сессия источника: cookies + sticky egress + согласованный UA/TLS."""

    source: str
    cookies: Dict[str, str] = field(default_factory=dict)
    proxy_url: Optional[str] = None
    user_agent: Optional[str] = None
    impersonate_id: Optional[str] = None
    device_id: Optional[str] = None
    obtained_at: float = field(default_factory=time.time)
    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def age_seconds(self) -> float:
        return max(0.0, time.time() - float(self.obtained_at or 0.0))

    def sessionid(self) -> Optional[str]:
        v = self.cookies.get("sessionid")
        if v is not None and str(v).strip():
            return str(v)
        return None

    def to_public_dict(self) -> Dict[str, Any]:
        """Без полных значений секретных кук — для логов/метрик."""
        return {
            "source": self.source,
            "cookie_keys": sorted(self.cookies.keys()),
            "has_sessionid": bool(self.sessionid()),
            "proxy_set": bool(self.proxy_url),
            "user_agent": (self.user_agent or "")[:80],
            "impersonate_id": self.impersonate_id,
            "device_id": self.device_id,
            "age_seconds": round(self.age_seconds, 1),
            "meta": dict(self.meta or {}),
        }

    @classmethod
    def from_mapping(cls, source: str, data: Mapping[str, Any]) -> "SessionBundle":
        cookies = data.get("cookies") if isinstance(data.get("cookies"), dict) else {}
        return cls(
            source=source,
            cookies={str(k): str(v) for k, v in cookies.items() if v is not None},
            proxy_url=str(data["proxy_url"]).strip() if data.get("proxy_url") else None,
            user_agent=str(data["user_agent"]) if data.get("user_agent") else None,
            impersonate_id=str(data["impersonate_id"]) if data.get("impersonate_id") else None,
            device_id=str(data["device_id"]) if data.get("device_id") else None,
            obtained_at=float(data.get("obtained_at") or time.time()),
            meta=dict(data.get("meta") or {}) if isinstance(data.get("meta"), dict) else {},
        )

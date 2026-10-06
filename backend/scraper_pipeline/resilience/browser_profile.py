"""Согласованный Chrome-профиль: UA + curl_cffi impersonate + sec-ch-ua."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional


# Pin major Chrome so TLS JA3 (impersonate) matches Client Hints / User-Agent.
_PROFILE_TABLE: Dict[str, Dict[str, str]] = {
    "chrome120": {
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "sec_ch_ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    },
    "chrome124": {
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "sec_ch_ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    },
    "chrome131": {
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "sec_ch_ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    },
    "chrome136": {
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
        ),
        "sec_ch_ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
    },
}

# Aliases → canonical impersonate id
_ALIASES: Dict[str, str] = {
    "chrome": "chrome131",
    "chrome_latest": "chrome131",
}


@dataclass(frozen=True)
class BrowserProfile:
    """Один identity на сессию: TLS impersonate + UA + Client Hints."""

    impersonate: str
    user_agent: str
    sec_ch_ua: str
    sec_ch_ua_mobile: str = "?0"
    sec_ch_ua_platform: str = '"Windows"'
    accept_language: str = "en-US,en;q=0.9"

    def default_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": self.user_agent,
            "Accept-Language": self.accept_language,
            "sec-ch-ua": self.sec_ch_ua,
            "sec-ch-ua-mobile": self.sec_ch_ua_mobile,
            "sec-ch-ua-platform": self.sec_ch_ua_platform,
        }


def normalize_impersonate(raw: Optional[str]) -> str:
    key = str(raw or "chrome131").strip().lower() or "chrome131"
    key = _ALIASES.get(key, key)
    if key not in _PROFILE_TABLE:
        # Unknown pin → chrome131 (safe default for curl_cffi).
        return "chrome131"
    return key


def resolve_browser_profile(config: Optional[Mapping[str, Any]] = None) -> BrowserProfile:
    """
    Читает http.impersonate (или resilience.impersonate) из конфига скрейпера.
    При transport=curl_cffi UA из user_agents игнорируется в пользу профиля.
    """
    cfg = dict(config or {})
    http = cfg.get("http") if isinstance(cfg.get("http"), dict) else {}
    res = cfg.get("resilience") if isinstance(cfg.get("resilience"), dict) else {}
    raw = http.get("impersonate") if http.get("impersonate") is not None else res.get("impersonate")
    impersonate = normalize_impersonate(str(raw) if raw is not None else None)
    row = _PROFILE_TABLE[impersonate]
    return BrowserProfile(
        impersonate=impersonate,
        user_agent=row["user_agent"],
        sec_ch_ua=row["sec_ch_ua"],
    )


def list_known_impersonates() -> tuple[str, ...]:
    return tuple(sorted(_PROFILE_TABLE.keys()))

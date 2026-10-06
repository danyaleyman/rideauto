"""
Challenge escalation L0–L3 (no third-party CAPTCHA farms).

L0 — normal HTTP (impersonate)
L1 — Playwright session refresh (headless)
L2 — headful Playwright refresh
L3 — cookie inject from secrets file
Human — still blocked: raise ChallengeNeedsHumanError (ops playbook)
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, Optional

from scraper_pipeline.resilience.policy import ResiliencePolicy

_CHALLENGE_RE = re.compile(
    r"cf-browser-verification|challenge-platform|captcha|hcaptcha|recaptcha|"
    r"access\s*denied|just\s*a\s*moment|attention\s*required|bot\s*detect",
    re.I,
)


class EscalationLevel(IntEnum):
    L0_HTTP = 0
    L1_SESSION_HEADLESS = 1
    L2_SESSION_HEADFUL = 2
    L3_COOKIE_INJECT = 3
    HUMAN = 4


@dataclass(frozen=True)
class ChallengeSignal:
    kind: str
    detail: str
    http_status: int = 0


class ChallengeDeferredError(RuntimeError):
    """Backward-compatible alias for hard challenge without auto path."""


class ChallengeNeedsHumanError(ChallengeDeferredError):
    """CAPTCHA/WAF needs operator cookie inject or policy change."""


def detect_challenge(
    *,
    http_status: int = 0,
    body_text: str = "",
    content_type: str = "",
) -> Optional[ChallengeSignal]:
    st = int(http_status or 0)
    text = (body_text or "")[:8000]
    ct = (content_type or "").lower()
    m = _CHALLENGE_RE.search(text)
    if not m:
        return None
    detail = m.group(0)
    if st in (401, 403, 503):
        return ChallengeSignal(kind="http_interstitial", detail=detail, http_status=st)
    if "html" in ct:
        return ChallengeSignal(kind="html_challenge", detail=detail, http_status=st)
    if "just a moment" in text.lower() or "cf-" in text.lower():
        return ChallengeSignal(kind="waf_challenge", detail=detail, http_status=st)
    return ChallengeSignal(kind="generic_challenge", detail=detail, http_status=st)


def max_auto_level(config: Optional[Dict[str, Any]] = None) -> EscalationLevel:
    res = (config or {}).get("resilience") if isinstance((config or {}).get("resilience"), dict) else {}
    raw = (res or {}).get("challenge_max_level")
    if raw is None:
        raw = os.environ.get("WRA_CHALLENGE_MAX_LEVEL", "3")
    try:
        n = int(raw)
    except (TypeError, ValueError):
        n = 3
    n = max(0, min(3, n))
    return EscalationLevel(n)


def cookie_inject_path(config: Optional[Dict[str, Any]] = None) -> Optional[Path]:
    res = (config or {}).get("resilience") if isinstance((config or {}).get("resilience"), dict) else {}
    p = str((res or {}).get("cookie_inject_path") or os.environ.get("WRA_COOKIE_INJECT_PATH") or "").strip()
    return Path(p) if p else None


def load_cookie_inject_file(path: Path) -> Dict[str, str]:
    """JSON object {name: value} or Netscape-ish list of {name,value}."""
    data = json.loads(path.read_text(encoding="utf-8"))
    out: Dict[str, str] = {}
    if isinstance(data, dict):
        for k, v in data.items():
            if v is not None and str(v).strip():
                out[str(k)] = str(v)
        return out
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and item.get("name") and item.get("value") is not None:
                out[str(item["name"])] = str(item["value"])
        return out
    raise ValueError(f"cookie inject file must be object or list: {path}")


def apply_cookie_inject_to_che168_config(config: dict, cookies: Dict[str, str], log: logging.Logger) -> None:
    ch = config.setdefault("che168", {})
    base = dict(ch.get("cookies") or {}) if isinstance(ch.get("cookies"), dict) else {}
    merged = {**base, **cookies}
    ch["cookies"] = merged
    if merged.get("sessionid"):
        ch["sessionid"] = merged["sessionid"]
    log.info("Challenge L3: injected %s cookies into che168 config", len(cookies))


def escalate_che168_session(
    config: dict,
    log: logging.Logger,
    *,
    level: EscalationLevel,
    policy: Optional[ResiliencePolicy] = None,
) -> EscalationLevel:
    """
    Run one escalation step for Che168. Returns the level that was executed.
    Raises ChallengeNeedsHumanError if level > max_auto or HUMAN required.
    """
    if policy is not None:
        policy.note_challenge_detected()
    ceiling = max_auto_level(config)
    if level > ceiling or level >= EscalationLevel.HUMAN:
        raise ChallengeNeedsHumanError(
            f"challenge_needs_human requested={int(level)} max_auto={int(ceiling)}; "
            f"place cookies at WRA_COOKIE_INJECT_PATH or raise WRA_CHALLENGE_MAX_LEVEL"
        )

    if level == EscalationLevel.L3_COOKIE_INJECT:
        path = cookie_inject_path(config)
        if not path or not path.is_file():
            raise ChallengeNeedsHumanError(
                "L3 cookie inject requested but WRA_COOKIE_INJECT_PATH missing/unreadable"
            )
        cookies = load_cookie_inject_file(path)
        apply_cookie_inject_to_che168_config(config, cookies, log)
        if policy is not None:
            policy.mark_session_refreshed()
        return level

    if level in (EscalationLevel.L1_SESSION_HEADLESS, EscalationLevel.L2_SESSION_HEADFUL):
        from scraper_pipeline.resilience.session_provider import apply_playwright_bootstrap_to_config

        ch = config.setdefault("che168", {})
        ch["playwright_headless"] = level != EscalationLevel.L2_SESSION_HEADFUL
        apply_playwright_bootstrap_to_config(config, log)
        if policy is not None:
            policy.mark_session_refreshed()
        return level

    # L0 — nothing to do (caller retries HTTP)
    return EscalationLevel.L0_HTTP


def handle_challenge_deferred(
    signal: ChallengeSignal,
    policy: Optional[ResiliencePolicy] = None,
) -> None:
    """Legacy entry: treat as needs-human unless auto path is configured elsewhere."""
    if policy is not None:
        policy.note_challenge_detected()
    raise ChallengeNeedsHumanError(
        f"challenge_detected kind={signal.kind} detail={signal.detail!r} "
        f"status={signal.http_status}; use escalate_che168_session L1–L3"
    )


def next_level_after_failure(current: EscalationLevel) -> EscalationLevel:
    if current >= EscalationLevel.HUMAN:
        return EscalationLevel.HUMAN
    return EscalationLevel(min(int(current) + 1, int(EscalationLevel.HUMAN)))

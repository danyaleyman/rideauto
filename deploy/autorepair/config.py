"""Конфигурация агента самовосстановления (только env, без секретов в коде)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _env_bool(name: str, default: bool = False) -> bool:
    v = (os.environ.get(name) or "").strip().lower()
    if not v:
        return default
    return v in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class AutorepairConfig:
    enabled: bool
    dry_run: bool
    interval_sec: int
    project_root: Path
    state_path: Path
    log_path: Path
    api_health_url: str
    web_url: str
    meili_health_url: str
    max_actions_per_hour: int
    cooldown_sec: int
    escalate_after_failures: int
    webhook_url: str
    meili_min_coverage: float
    allow_restart: bool
    allow_meili_sync: bool
    allow_migrate: bool

    @classmethod
    def from_env(cls) -> "AutorepairConfig":
        root = Path(os.environ.get("WRA_AUTOREPAIR_ROOT", str(_repo_root()))).resolve()
        var_dir = root / "var" / "autorepair"
        return cls(
            enabled=_env_bool("WRA_AUTOREPAIR_ENABLED", False),
            dry_run=_env_bool("WRA_AUTOREPAIR_DRY_RUN", True),
            interval_sec=max(5, _env_int("WRA_AUTOREPAIR_INTERVAL_SEC", 30)),
            project_root=root,
            state_path=Path(
                os.environ.get("WRA_AUTOREPAIR_STATE", str(var_dir / "state.json"))
            ).resolve(),
            log_path=Path(os.environ.get("WRA_AUTOREPAIR_LOG", str(var_dir / "events.log"))).resolve(),
            api_health_url=os.environ.get(
                "WRA_AUTOREPAIR_API_HEALTH", "http://127.0.0.1:8080/api/health?deep=1"
            ).strip(),
            web_url=os.environ.get("WRA_AUTOREPAIR_WEB_URL", "http://127.0.0.1:3000/").strip(),
            meili_health_url=os.environ.get(
                "WRA_AUTOREPAIR_MEILI_HEALTH", "http://127.0.0.1:7700/health"
            ).strip(),
            max_actions_per_hour=_env_int("WRA_AUTOREPAIR_MAX_ACTIONS_PER_HOUR", 20),
            cooldown_sec=_env_int("WRA_AUTOREPAIR_COOLDOWN_SEC", 300),
            escalate_after_failures=_env_int("WRA_AUTOREPAIR_ESCALATE_AFTER", 8),
            webhook_url=(os.environ.get("WRA_AUTOREPAIR_WEBHOOK_URL") or "").strip(),
            meili_min_coverage=float(os.environ.get("WRA_HEALTH_MEILI_MIN_COVERAGE_PCT", "90")),
            allow_restart=_env_bool("WRA_AUTOREPAIR_ALLOW_RESTART", True),
            allow_meili_sync=_env_bool("WRA_AUTOREPAIR_ALLOW_MEILI_SYNC", True),
            allow_migrate=_env_bool("WRA_AUTOREPAIR_ALLOW_MIGRATE", False),
        )

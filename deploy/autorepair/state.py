"""Состояние агента: cooldown действий, счётчик сбоев, журнал."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AutorepairState:
    last_actions: dict[str, float] = field(default_factory=dict)
    consecutive_failures: int = 0
    last_ok_at: float = 0.0
    last_incident_at: float = 0.0
    total_actions: int = 0
    actions_this_hour: list[float] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "AutorepairState":
        if not path.is_file():
            return cls()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return cls(
                last_actions={k: float(v) for k, v in (raw.get("last_actions") or {}).items()},
                consecutive_failures=int(raw.get("consecutive_failures") or 0),
                last_ok_at=float(raw.get("last_ok_at") or 0),
                last_incident_at=float(raw.get("last_incident_at") or 0),
                total_actions=int(raw.get("total_actions") or 0),
                actions_this_hour=[float(t) for t in (raw.get("actions_this_hour") or [])],
            )
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            return cls()

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "last_actions": self.last_actions,
            "consecutive_failures": self.consecutive_failures,
            "last_ok_at": self.last_ok_at,
            "last_incident_at": self.last_incident_at,
            "total_actions": self.total_actions,
            "actions_this_hour": self._prune_hour(),
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _prune_hour(self) -> list[float]:
        cutoff = time.time() - 3600
        return [t for t in self.actions_this_hour if t >= cutoff]

    def can_run_action(self, action_key: str, cooldown_sec: int, max_per_hour: int) -> bool:
        now = time.time()
        last = self.last_actions.get(action_key, 0.0)
        if now - last < cooldown_sec:
            return False
        if len(self._prune_hour()) >= max_per_hour:
            return False
        return True

    def record_action(self, action_key: str) -> None:
        now = time.time()
        self.last_actions[action_key] = now
        self.actions_this_hour = self._prune_hour() + [now]
        self.total_actions += 1

    def log_event(self, log_path: Path, event: dict[str, Any]) -> None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({"ts": time.time(), **event}, ensure_ascii=False)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

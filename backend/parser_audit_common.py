"""Общие утилиты для nightly-аудита парсеров (Encar / Che168) — печать секций, %, JSONL-история."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def audit_print_section(title: str, rows: list[tuple[Any, ...]]) -> None:
    print(f"\n## {title}")
    if not rows:
        print("(empty)")
        return
    for row in rows:
        print(" - " + " | ".join("" if v is None else str(v) for v in row))


def audit_pct(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((part / total) * 100.0, 2)


def audit_read_last_summary_from_history(history_file: str) -> dict[str, Any]:
    p = Path(history_file)
    if not p.is_file():
        return {}
    for line in reversed(p.read_text(encoding="utf-8").splitlines()):
        raw = line.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        summary = row.get("summary")
        if isinstance(summary, dict):
            return summary
    return {}


def audit_append_history(
    history_file: str, summary: dict[str, Any], delta: dict[str, Any]
) -> None:
    p = Path(history_file)
    p.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "delta": delta,
    }
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def audit_trim_history_file(history_file: str, keep_days: int) -> None:
    if keep_days <= 0:
        return
    p = Path(history_file)
    if not p.is_file():
        return
    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    kept: list[str] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            kept.append(line)
            continue
        ts_raw = row.get("ts")
        if not isinstance(ts_raw, str):
            kept.append(line)
            continue
        try:
            ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
        except ValueError:
            kept.append(line)
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts >= cutoff:
            kept.append(line)
    p.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")

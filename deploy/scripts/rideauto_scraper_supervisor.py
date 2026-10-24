#!/usr/bin/env python3
"""Keep Encar / Che168 / Autotrader scrapers alive until work drains; restart on death/stall.

Run:
  /opt/rideauto/.venv/bin/python /opt/rideauto/deploy/scripts/rideauto_scraper_supervisor.py
  # or systemd: rideauto-scraper-supervisor.service
"""

from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(os.environ.get("ROOT", "/opt/rideauto"))
LOG_DIR = ROOT / "logs" / "overnight"
STATE_DIR = ROOT / "logs" / "supervisor_state"
PY = ROOT / ".venv" / "bin" / "python"
BACKEND = ROOT / "backend"

INTERVAL = int(os.environ.get("WRA_SUPERVISOR_INTERVAL_SEC", "120"))
STALL_SEC = int(os.environ.get("WRA_SUPERVISOR_STALL_SEC", "900"))
CATALOG_EVERY = int(os.environ.get("WRA_SUPERVISOR_CATALOG_EVERY_SEC", "1800"))
# Сколько ждать уже запущенный catalog-пайплайн перед финальным sync (сек).
CATALOG_WAIT_SEC = int(os.environ.get("WRA_SUPERVISOR_CATALOG_WAIT_SEC", "14400"))
# Лимит памяти для catalog-пайплайна (systemd-scope). Пайплайн (дедуп держит
# весь каталог в RAM) требует ~14 ГБ; раньше он жил в cgroup супервизора и при
# 16 ГБ RAM без swap валил юнит по oom-kill (restart counter 71). Теперь он в
# отдельном scope с MemoryMax — при перерасходе умирает только сам пайплайн.
CATALOG_MEM_MAX = (os.environ.get("WRA_SUPERVISOR_CATALOG_MEM_MAX") or "12G").strip()
# Final/periodic catalog kick: skip postgres_catalog_sync (OOM on 16G hosts).
# Nightly rideauto-catalog-pipeline.timer still runs full PG+Meili when resources allow.
CATALOG_SKIP_PG = (os.environ.get("WRA_SUPERVISOR_CATALOG_SKIP_PG") or "1").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
# pending==0 must hold this many supervisor ticks before COMPLETE (false COMPLETE guard).
COMPLETE_CONFIRM_TICKS = max(1, int(os.environ.get("WRA_SUPERVISOR_COMPLETE_CONFIRM_TICKS", "2")))
FINAL_SYNC_MARKER = "final_sync.done"
# Stop restarting Autotrader after N consecutive clean finishes with almost no new saves.
AT_IDLE_STOP = int(os.environ.get("WRA_SUPERVISOR_AT_IDLE_STOP", "3"))
# parallel (default) | sequential — one market at a time in WRA_SUPERVISOR_ORDER
MODE = (os.environ.get("WRA_SUPERVISOR_MODE") or "parallel").strip().lower()
ORDER = [
    x.strip()
    for x in (os.environ.get("WRA_SUPERVISOR_ORDER") or "encar,che168,autotrader").split(",")
    if x.strip()
]


def log(msg: str) -> None:
    print(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} [supervisor] {msg}", flush=True)


def load_env() -> None:
    for path in (Path("/etc/default/rideauto"), ROOT / ".env"):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def pg_dsn() -> str:
    raw = os.environ.get("SYNC_PG_DSN") or os.environ.get("DATABASE_URL") or os.environ.get("WRA_PG_DSN") or ""
    rewrite = ROOT / "deploy" / "scripts" / "pg_dsn_host_local_rewrite.py"
    if rewrite.is_file() and raw:
        raw = subprocess.check_output([sys.executable, str(rewrite)], input=raw.encode()).decode().strip()
    return raw


def pg_snapshot() -> Dict[str, int]:
    import psycopg2

    conn = psycopg2.connect(pg_dsn())
    cur = conn.cursor()
    cur.execute("SELECT coalesce(source,''), count(*) FROM cars GROUP BY 1")
    counts = {str(k): int(v) for k, v in cur.fetchall()}
    pending = {"encar": -1, "che168": -1, "autotrader": -1}
    try:
        cur.execute(
            "SELECT scope, COUNT(*) FROM scraper_pending_ids "
            "WHERE scope IN ('encar','che168','autotrader') GROUP BY scope"
        )
        for scope, n in cur.fetchall():
            pending[str(scope)] = int(n or 0)
        # Оба запроса прошли => таблица читается: отсутствие строк для scope = очередь
        # разобрана (0). -1 остаётся только когда чтение pending упало (см. except).
        for scope in ("encar", "che168", "autotrader"):
            if pending[scope] < 0:
                pending[scope] = 0
    except Exception:
        conn.rollback()
    conn.close()
    return {
        "encar": counts.get("encar", 0),
        "che168": counts.get("che168", 0),
        "autotrader": counts.get("autotrader", 0),
        "pending_encar": pending["encar"],
        "pending_che168": pending["che168"],
        "pending_autotrader": pending["autotrader"],
    }


def pids_for(pattern: str) -> List[int]:
    try:
        out = subprocess.check_output(["pgrep", "-f", pattern], text=True)
    except subprocess.CalledProcessError:
        return []
    return [int(x) for x in out.split() if x.strip().isdigit()]


def kill_pattern(pattern: str) -> None:
    subprocess.run(["pkill", "-f", pattern], check=False)
    time.sleep(2)
    # force leftovers
    for pid in pids_for(pattern):
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass


def _env_truthy(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in ("1", "true", "yes", "on")


def start_as_rideauto(cmd: List[str], logfile: Path) -> None:
    logfile.parent.mkdir(parents=True, exist_ok=True)
    logfile.touch(exist_ok=True)
    try:
        subprocess.run(["chown", "rideauto:rideauto", str(logfile)], check=False)
    except Exception:
        pass
    inner = (
        "set -a; "
        "[[ -f /etc/default/rideauto ]] && . /etc/default/rideauto; "
        f"[[ -f {ROOT}/.env ]] && . {ROOT}/.env; "
        "set +a; "
        # Скраперы не должны сами гонять postgres_catalog_sync: этот пайплайн
        # (прайсинг полного каталога) съедает ~14 ГБ и живёт в cgroup супервизора,
        # из-за чего юнит падал по oom-kill (71 рестарт). Каталог синхронизирует
        # сам супервизор — в отдельном systemd-scope с MemoryMax.
        # Переопределить можно в /etc/default/rideauto (SKIP_*=0).
        'export SKIP_POSTGRES_CATALOG_SYNC="${SKIP_POSTGRES_CATALOG_SYNC:-1}"; '
        'export SKIP_FRONTEND_EXPORT="${SKIP_FRONTEND_EXPORT:-1}"; '
        f"cd {ROOT}; "
        f"nohup {' '.join(cmd)} >>{logfile} 2>&1 &"
    )
    subprocess.Popen(
        [
            "sudo",
            "-u",
            "rideauto",
            "env",
            "HOME=/var/lib/rideauto",
            "PYTHONUNBUFFERED=1",
            f"PYTHONPATH={BACKEND}",
            "bash",
            "-lc",
            inner,
        ]
    )


@dataclass
class Market:
    name: str
    pattern: str
    log_glob: str
    start_cmd: List[str]
    last_count: int = 0
    last_progress_ts: float = field(default_factory=time.time)
    idle_finishes: int = 0
    complete: bool = False
    complete_ticks: int = 0


def complete_marker_path(state_dir: Path, market: str) -> Path:
    return state_dir / f"{market}.complete"


def final_sync_marker_path(state_dir: Path) -> Path:
    return state_dir / FINAL_SYNC_MARKER


def load_complete_markers(markets: List[Market], state_dir: Path) -> None:
    """Restore COMPLETE from disk so Restart=always does not re-scrape finished markets."""
    for m in markets:
        p = complete_marker_path(state_dir, m.name)
        if p.is_file():
            m.complete = True
            m.complete_ticks = COMPLETE_CONFIRM_TICKS
            log(f"{m.name}: COMPLETE (marker {p.name})")


def market_ready_for_complete(
    *,
    pending: int,
    running: bool,
    log_done: bool,
    pg_count: int,
) -> bool:
    """Single-tick COMPLETE predicate (still needs confirm ticks in the main loop)."""
    return pending == 0 and (not running) and log_done and pg_count > 0


def note_complete_tick(m: Market, ready: bool, required_ticks: int) -> bool:
    """Return True when market just became COMPLETE after enough ready ticks."""
    if not ready:
        m.complete_ticks = 0
        return False
    m.complete_ticks += 1
    return m.complete_ticks >= required_ticks


def latest_log(glob_pat: str) -> Optional[Path]:
    files = sorted(LOG_DIR.glob(glob_pat), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def log_mentions_done(path: Optional[Path]) -> bool:
    if not path or not path.is_file():
        return False
    try:
        tail = path.read_text(encoding="utf-8", errors="ignore")[-8000:]
    except OSError:
        return False
    return bool(
        re.search(
            r"(ingest done|scraper finished|завершен|completed successfully|only-pending done)",
            tail,
            re.I,
        )
    )


def ensure_meili_helper() -> Path:
    helper = Path("/tmp/rideauto_meili_sync.sh")
    helper.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
ROOT=/opt/rideauto
cd "$ROOT"
set -a
[[ -f /etc/default/rideauto ]] && . /etc/default/rideauto
[[ -f "$ROOT/.env" ]] && . "$ROOT/.env"
set +a
PG_DSN="${SYNC_PG_DSN:-${DATABASE_URL:-${WRA_PG_DSN:-}}}"
REWRITE_PY="$ROOT/deploy/scripts/pg_dsn_host_local_rewrite.py"
[[ -f "$REWRITE_PY" ]] && PG_DSN="$(printf '%s' "$PG_DSN" | /usr/bin/python3 "$REWRITE_PY")"
MEILI_KEY="${MEILI_MASTER_KEY:-${WRA_MEILISEARCH_KEY:-}}"
ARGS=(--pg-dsn "$PG_DSN" --meili-url "${WRA_MEILISEARCH_URL:-http://127.0.0.1:7700}" --index-name "${WRA_MEILISEARCH_INDEX:-cars}" --settings "${WRA_MEILISEARCH_SETTINGS:-$ROOT/infrastructure/meilisearch/index_settings.json}" --batch-size "${MEILISEARCH_SYNC_BATCH:-500}")
[[ -n "$MEILI_KEY" ]] && ARGS+=(--meili-key "$MEILI_KEY")
"$ROOT/.venv/bin/python" "$ROOT/infrastructure/meilisearch/sync_meilisearch.py" "${ARGS[@]}"
""",
        encoding="utf-8",
    )
    helper.chmod(0o755)
    return helper


def catalog_pids() -> List[int]:
    """PIDs живого catalog-пайплайна (postgres_catalog_sync -> meili sync)."""
    return pids_for("run_catalog_pipeline_host.sh")


def wait_catalog(timeout: int) -> None:
    """Дождаться завершения уже запущенного catalog-пайплайна (не дольше timeout)."""
    deadline = time.time() + max(0, timeout)
    while time.time() < deadline and catalog_pids():
        time.sleep(30)


def catalog_scope_cmd() -> List[str]:
    """Обёртка запуска catalog-пайплайна в отдельном systemd-scope с MemoryMax.

    Scope создаётся как самостоятельный юнит: его OOM не убивает cgroup
    супервизора, и он переживает рестарт супервизора. Без systemd-run
    деградируем до setsid (прежнее поведение).
    """
    if not shutil.which("systemd-run"):
        return ["setsid"]
    unit = "rideauto-catalog-sync-" + time.strftime("%Y%m%d%H%M%S")
    return [
        "systemd-run",
        "--scope",
        "--quiet",
        "--collect",
        f"--unit={unit}",
        f"--property=MemoryMax={CATALOG_MEM_MAX}",
    ]


def _catalog_env(*, skip_pg: bool) -> dict:
    env = os.environ.copy()
    if skip_pg:
        env["WRA_CATALOG_PIPELINE_SKIP_PG"] = "1"
    return env


def kick_catalog_bg() -> bool:
    """Неблокирующий catalog kick (периодический).

    По умолчанию meili-only: полный postgres_catalog_sync OOMit в scope 12G
    на 16G хосте (prod 2026-10-10). Дубли исключает catalog_pids().
    """
    pids = catalog_pids()
    if pids:
        log(f"catalog pipeline already running pids={pids} -> skip kick")
        return False
    pipe = ROOT / "deploy" / "scripts" / "run_catalog_pipeline_host.sh"
    out = LOG_DIR / "catalog_supervisor.log"
    skip_pg = CATALOG_SKIP_PG
    try:
        with out.open("a", encoding="utf-8") as fh:
            mode = "meili-only" if skip_pg else "full"
            fh.write(
                f"=== catalog pipeline start {time.strftime('%Y-%m-%dT%H:%M:%S%z')} "
                f"(async,{mode}) ===\n"
            )
            fh.flush()
            # meili-only: без MemoryMax-scope (раньше scope убивал PG-стадию по OOM).
            cmd = (["bash", str(pipe)] if skip_pg else catalog_scope_cmd() + ["bash", str(pipe)])
            subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=fh,
                stderr=fh,
                start_new_session=True,
                env=_catalog_env(skip_pg=skip_pg),
            )
    except Exception as e:
        log(f"catalog kick failed: {e}")
        return False
    log(f"catalog sync kick (async, {'meili-only' if skip_pg else 'full'})")
    return True


def kick_catalog() -> None:
    """Blocking catalog sync after markets complete (search catch-up).

    Full postgres_catalog_sync holds ~12G+ RSS and OOMs under MemoryMax=12G on a
    16G host (rc=-15 / SIGTERM). Default: Meili only; nightly timer still does PG.
    """
    if final_sync_marker_path(STATE_DIR).is_file():
        log("final sync marker present -> skip catalog kick")
        return
    skip_pg = CATALOG_SKIP_PG
    log(
        "catalog sync kick (blocking, "
        + ("meili-only — skip PG to avoid OOM)" if skip_pg else "full pipeline)")
    )
    pipe = ROOT / "deploy" / "scripts" / "run_catalog_pipeline_host.sh"
    out = LOG_DIR / "catalog_supervisor.log"
    env = _catalog_env(skip_pg=skip_pg)
    try:
        with out.open("a", encoding="utf-8") as fh:
            cmd = ["bash", str(pipe)] if skip_pg else catalog_scope_cmd() + ["bash", str(pipe)]
            rc = subprocess.call(cmd, stdout=fh, stderr=fh, env=env)
        if rc == 0:
            log("catalog pipeline ok" + (" (meili-only)" if skip_pg else ""))
            final_sync_marker_path(STATE_DIR).write_text(
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), encoding="utf-8"
            )
            return
        log(f"catalog pipeline rc={rc}; meili helper fallback")
    except Exception as e:
        log(f"catalog pipeline error: {e}")
    helper = ensure_meili_helper()
    with out.open("a", encoding="utf-8") as fh:
        rc2 = subprocess.call(["bash", str(helper)], stdout=fh, stderr=fh)
    if rc2 == 0:
        final_sync_marker_path(STATE_DIR).write_text(
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), encoding="utf-8"
        )


def build_markets(*, sequential: bool) -> List[Market]:
    """In sequential full-dump mode Che168 runs list+detail (not --only-pending)."""
    che168_cmd = [
        str(PY),
        str(BACKEND / "che168_scraper.py"),
        "--config",
        str(ROOT / "che168_scraper.yaml"),
        "--max-cars",
        "0",
    ]
    if not sequential:
        che168_cmd.append("--only-pending")
    # Autotrader: default phase comes from autotrader_scraper.yaml (all = discovery + detail).
    # WRA_SUPERVISOR_AT_PHASE lets ops pin the phase without editing the YAML
    # (e.g. "list" to refill scraper_pending_ids, "detail" to drain the backlog).
    # WRA_SUPERVISOR_AT_SPLIT=1 → два процесса (list + detail) вместо phase=all:
    # стабильнее при Akamai (SRP не делит Chromium с VDP). Не сочетать с AT_PHASE=list|detail.
    # NB: пиннинг "list"/"detail" — это ops-режим на один прогон: пока в pending есть
    # строки, супервизор не считает рынок завершённым и будет перезапускать его снова.
    at_cmd = [
        str(PY),
        str(BACKEND / "autotrader_scraper.py"),
        "--config",
        str(ROOT / "autotrader_scraper.yaml"),
    ]
    at_phase = (os.environ.get("WRA_SUPERVISOR_AT_PHASE") or "").strip().lower()
    if at_phase in ("all", "list", "detail", "only-pending"):
        at_cmd += ["--phase", "detail" if at_phase == "only-pending" else at_phase]
    by_name = {
        "encar": Market(
            name="encar",
            pattern="backend/encar_scraper.py",
            log_glob="encar_*.log",
            start_cmd=[
                str(PY),
                str(BACKEND / "encar_scraper.py"),
                "--config",
                str(ROOT / "scraper_config.yaml"),
                "--max-cars",
                "0",
            ],
        ),
        "che168": Market(
            name="che168",
            pattern="backend/che168_scraper.py",
            log_glob="che168_*.log",
            start_cmd=che168_cmd,
        ),
        "autotrader": Market(
            name="autotrader",
            pattern="backend/autotrader_scraper.py",
            log_glob="autotrader_*.log",
            start_cmd=at_cmd,
        ),
    }
    order = ORDER if sequential else list(by_name.keys())
    out: List[Market] = []
    for name in order:
        m = by_name.get(name)
        if m is None:
            log(f"unknown market in ORDER: {name}")
            continue
        out.append(m)
    return out


def active_sequential_market(markets: List[Market]) -> Optional[Market]:
    for m in markets:
        if not m.complete:
            return m
    return None


def _autotrader_phase_pids(phase: str) -> List[int]:
    """PIDs for a specific Autotrader --phase (list|detail)."""
    return pids_for(f"backend/autotrader_scraper.py.*--phase {phase}")


def _start_autotrader_phase(phase: str, stamp: str) -> None:
    base = [
        str(PY),
        str(BACKEND / "autotrader_scraper.py"),
        "--config",
        str(ROOT / "autotrader_scraper.yaml"),
        "--phase",
        phase,
    ]
    lf = LOG_DIR / f"autotrader_{phase}_{stamp}.log"
    log(f"autotrader: start phase={phase}")
    start_as_rideauto(base, lf)


def _start_market(m: Market, stamp: str) -> None:
    """Старт рынка. Для Autotrader при AT_SPLIT=1 — два процесса list+detail."""
    if m.name == "autotrader" and _env_truthy("WRA_SUPERVISOR_AT_SPLIT"):
        pinned = (os.environ.get("WRA_SUPERVISOR_AT_PHASE") or "").strip().lower()
        if pinned in ("list", "detail", "only-pending"):
            log(f"autotrader: AT_SPLIT ignored (AT_PHASE={pinned})")
        else:
            log("autotrader: start SPLIT list+detail")
            _start_autotrader_phase("list", stamp)
            time.sleep(1)
            _start_autotrader_phase("detail", stamp)
            return
    lf = LOG_DIR / f"{m.name}_sup_{stamp}.log"
    start_as_rideauto(m.start_cmd, lf)


def main() -> int:
    global MODE
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    load_env()
    MODE = (os.environ.get("WRA_SUPERVISOR_MODE") or MODE or "parallel").strip().lower()
    sequential = MODE in ("sequential", "seq", "one")
    at_split = _env_truthy("WRA_SUPERVISOR_AT_SPLIT")
    at_phase = (os.environ.get("WRA_SUPERVISOR_AT_PHASE") or "").strip() or "-"
    log(
        f"boot mode={MODE} order={ORDER if sequential else 'all'} "
        f"interval={INTERVAL}s stall={STALL_SEC}s catalog_every={CATALOG_EVERY}s "
        f"at_phase={at_phase} at_split={int(at_split)}"
    )

    markets = build_markets(sequential=sequential)
    load_complete_markers(markets, STATE_DIR)

    # НЕ 0.0: иначе "now - last_catalog >= CATALOG_EVERY" истинно на первом же
    # витке после рестарта и супервизор снова поднимает 14-ГБ catalog-пайплайн
    # (это валило юнит по OOM). Отсчёт идёт от старта процесса.
    last_catalog = time.time()
    log(f"catalog auto-kick: {'disabled' if CATALOG_EVERY <= 0 else f'every {CATALOG_EVERY}s from boot'}")
    log(
        f"catalog skip_pg={int(CATALOG_SKIP_PG)} complete_confirm_ticks={COMPLETE_CONFIRM_TICKS} "
        f"final_sync_marker={int(final_sync_marker_path(STATE_DIR).is_file())}"
    )
    snap = pg_snapshot()
    for m in markets:
        m.last_count = int(snap.get(m.name, 0))
        m.last_progress_ts = time.time()

    while True:
        load_env()
        MODE = (os.environ.get("WRA_SUPERVISOR_MODE") or MODE or "parallel").strip().lower()
        sequential = MODE in ("sequential", "seq", "one")
        try:
            snap = pg_snapshot()
        except Exception as e:
            log(f"pg snapshot failed: {e}")
            snap = {}

        now = time.time()
        focus = active_sequential_market(markets) if sequential else None
        if sequential and focus:
            # Hard-stop every other market so only one scrape burns CPU/proxy.
            for m in markets:
                if m.name == focus.name:
                    continue
                if pids_for(m.pattern):
                    log(f"sequential: kill idle market {m.name} (focus={focus.name})")
                    kill_pattern(m.pattern)

        for m in markets:
            if m.complete:
                continue
            if sequential and focus is not None and m.name != focus.name:
                continue

            count = int(snap.get(m.name, m.last_count))
            # All three markets now publish their backlog into scraper_pending_ids
            # (autotrader = two-phase discovery → pending → detail). -1 = count unknown.
            pending = int(snap.get(f"pending_{m.name}", -1))

            if count > m.last_count:
                m.last_count = count
                m.last_progress_ts = now
                m.idle_finishes = 0

            at_split = m.name == "autotrader" and _env_truthy("WRA_SUPERVISOR_AT_SPLIT")
            list_pids = _autotrader_phase_pids("list") if at_split else []
            detail_pids = _autotrader_phase_pids("detail") if at_split else []
            running = bool(pids_for(m.pattern))
            latest = latest_log(m.log_glob)

            # Completion heuristics: require pending=0 for COMPLETE_CONFIRM_TICKS
            # consecutive ticks so a transient empty queue mid-dump cannot fake COMPLETE.
            ready = market_ready_for_complete(
                pending=pending,
                running=running,
                log_done=log_mentions_done(latest),
                pg_count=count,
            )
            if note_complete_tick(m, ready, COMPLETE_CONFIRM_TICKS):
                m.complete = True
                log(
                    f"{m.name}: COMPLETE pending=0 "
                    f"(confirmed {COMPLETE_CONFIRM_TICKS} ticks) → next"
                    if sequential
                    else f"{m.name}: COMPLETE pending=0 (confirmed {COMPLETE_CONFIRM_TICKS} ticks)"
                )
                complete_marker_path(STATE_DIR, m.name).write_text(
                    time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), encoding="utf-8"
                )
                continue
            if ready and not m.complete:
                log(
                    f"{m.name}: complete candidate pending=0 "
                    f"tick={m.complete_ticks}/{COMPLETE_CONFIRM_TICKS}"
                )

            if at_split and running:
                # SPLIT: list и detail живут раздельно — поднимаем упавший хвост,
                # не убивая живой discovery.
                stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
                if not list_pids:
                    log(f"autotrader: list dead -> start (pg={count} pending={pending})")
                    _start_autotrader_phase("list", stamp)
                    m.last_progress_ts = now
                    time.sleep(2)
                if not detail_pids:
                    log(f"autotrader: detail dead -> start (pg={count} pending={pending})")
                    _start_autotrader_phase("detail", stamp)
                    m.last_progress_ts = now
                    time.sleep(2)

            if not running:
                # Autotrader finished cleanly with no growth → count idle finishes
                # (fallback for when the pending backlog cannot be read: pending == -1).
                if m.name == "autotrader" and pending < 0 and log_mentions_done(latest):
                    m.idle_finishes += 1
                    log(f"autotrader: clean finish idle={m.idle_finishes}/{AT_IDLE_STOP} count={count}")
                    if m.idle_finishes >= AT_IDLE_STOP:
                        m.complete = True
                        log("autotrader: COMPLETE (idle finishes)")
                        STATE_DIR.joinpath("autotrader.complete").write_text(
                            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), encoding="utf-8"
                        )
                        continue
                log(f"{m.name}: dead -> start (pg={count} pending={pending})")
                stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
                _start_market(m, stamp)
                m.last_progress_ts = now
                time.sleep(3)
                continue

            stalled = (now - m.last_progress_ts) >= STALL_SEC
            # Restart only when there is work left: pending > 0, or (autotrader)
            # pending unknown (-1) so we never give up on a stalled drain.
            if stalled and (pending > 0 or (m.name == "autotrader" and pending < 0)):
                log(
                    f"{m.name}: STALL {int(now - m.last_progress_ts)}s "
                    f"pg={count} pending={pending} -> restart"
                )
                kill_pattern(m.pattern)
                time.sleep(2)
                stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
                _start_market(m, stamp)
                m.last_progress_ts = now
                continue

            if at_split:
                log(
                    f"{m.name}: ok split list={len(list_pids)} detail={len(detail_pids)} "
                    f"pg={count} pending={pending}"
                )
            else:
                log(f"{m.name}: ok running pg={count} pending={pending}")

        if CATALOG_EVERY > 0 and now - last_catalog >= CATALOG_EVERY:
            try:
                kick_catalog_bg()
            except Exception as e:
                log(f"catalog kick failed: {e}")
            last_catalog = now

        if all(m.complete for m in markets):
            # Do not exit: systemd Restart=always would restart us, see encar.complete,
            # re-run final sync (often OOM on postgres_catalog_sync), and loop forever.
            log("all markets complete -> final catalog sync, then idle")
            pids = catalog_pids()
            if pids:
                log(f"catalog pipeline still running pids={pids} -> wait (max {CATALOG_WAIT_SEC}s)")
                wait_catalog(CATALOG_WAIT_SEC)
            else:
                kick_catalog()
            log("idle (markets complete); sleeping — stop unit or clear supervisor_state to resume")
            while True:
                time.sleep(max(3600, INTERVAL))

        time.sleep(INTERVAL)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        log("interrupted")
        raise SystemExit(0)

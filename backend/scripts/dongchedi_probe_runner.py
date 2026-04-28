from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import psycopg2


def _parse_images(raw: Any) -> List[str]:
    value = raw
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return []
        try:
            value = json.loads(s)
        except Exception:
            return [s] if s.startswith("http") else []
    if not isinstance(value, list):
        return []
    out: List[str] = []
    for item in value:
        if isinstance(item, str) and item.startswith("http"):
            out.append(item)
        elif isinstance(item, dict):
            u = item.get("url") or item.get("imageUrl") or item.get("src")
            if isinstance(u, str) and u.startswith("http"):
                out.append(u)
    return out


def _parse_jsonish(raw: Any) -> Any:
    if isinstance(raw, (dict, list)):
        return raw
    if not isinstance(raw, str):
        return raw
    s = raw.strip()
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        return raw


@dataclass
class ProbeMetrics:
    run: int
    return_code: int
    elapsed_sec: float
    total_rows: int
    with_ge2_images: int
    with_ge5_images: int
    single_image_rows: int
    with_configuration: int
    with_recommended_options: int


def _connect(database_url: str):
    return psycopg2.connect(database_url)


def _delete_china(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM cars WHERE source='dongchedi';")
    conn.commit()


def _collect_metrics(conn, limit: int) -> Dict[str, int]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT car_id, data
            FROM cars
            WHERE source='dongchedi'
            ORDER BY updated_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()

    total = len(rows)
    ge2 = 0
    ge5 = 0
    single = 0
    with_cfg = 0
    with_opts = 0

    for _, payload in rows:
        p = _parse_jsonish(payload) or {}
        data = p.get("data") if isinstance(p, dict) else {}
        if not isinstance(data, dict):
            data = {}
        images = _parse_images(data.get("images"))
        n = len(images)
        if n >= 2:
            ge2 += 1
        if n >= 5:
            ge5 += 1
        if n == 1:
            single += 1
        if str(data.get("configuration") or "").strip():
            with_cfg += 1
        opts = _parse_jsonish(data.get("dongchedi_recommended_options"))
        if isinstance(opts, list) and len(opts) > 0:
            with_opts += 1

    return {
        "total_rows": total,
        "with_ge2_images": ge2,
        "with_ge5_images": ge5,
        "single_image_rows": single,
        "with_configuration": with_cfg,
        "with_recommended_options": with_opts,
    }


def _default_checkpoint_path(db_path: str) -> str:
    p = Path(db_path).resolve()
    return str(p.with_name(p.stem + ".scraper.checkpoint.json"))


def _run_scraper(cmd: List[str], cwd: str) -> tuple[int, float]:
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, cwd=cwd, check=False)
    elapsed = time.perf_counter() - t0
    return proc.returncode, elapsed


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Run repeated Dongchedi probe scrapes and print quality metrics."
    )
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--config", required=True)
    ap.add_argument("--db-path", default="encar_china.db")
    ap.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    ap.add_argument("--python-bin", default=sys.executable)
    ap.add_argument("--backend-dir", default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument("--reset-between-runs", action="store_true")
    ap.add_argument("--session-user-data-dir", default="")
    ap.add_argument("--browser-fallback", action="store_true", default=True)
    ap.add_argument("--concurrency", type=int, default=2)
    ap.add_argument("--detail-concurrency", type=int, default=1)
    ap.add_argument("--session-refresh-sec", type=float, default=1200.0)
    ap.add_argument("--session-refresh-min-interval-s", type=float, default=90.0)
    args = ap.parse_args()

    dsn = (args.database_url or "").strip()
    if not dsn:
        print("ERROR: database URL is required (--database-url or DATABASE_URL env).")
        return 2

    cfg_path = str(Path(args.config).resolve())
    backend_dir = str(Path(args.backend_dir).resolve())
    db_path = str(Path(args.db_path).resolve())
    checkpoint_path = _default_checkpoint_path(db_path)

    conn = _connect(dsn)
    results: List[ProbeMetrics] = []
    try:
        for i in range(1, max(1, int(args.runs)) + 1):
            if args.reset_between_runs:
                _delete_china(conn)
                if Path(checkpoint_path).exists():
                    Path(checkpoint_path).unlink(missing_ok=True)

            cmd = [
                args.python_bin,
                "-m",
                "dongchedi.scraper",
                "--config",
                cfg_path,
                "--db",
                db_path,
                "--shard-brands",
                "--limit",
                str(max(1, int(args.limit))),
                "--concurrency",
                str(max(1, int(args.concurrency))),
                "--detail-concurrency",
                str(max(1, int(args.detail_concurrency))),
                "--session-refresh-sec",
                str(max(60.0, float(args.session_refresh_sec))),
                "--session-refresh-min-interval-s",
                str(max(5.0, float(args.session_refresh_min_interval_s))),
            ]
            if args.browser_fallback:
                cmd.append("--browser-fallback")
            if args.session_user_data_dir.strip():
                cmd.extend(["--session-user-data-dir", args.session_user_data_dir.strip()])

            print(f"\n=== Probe run {i}/{args.runs} ===")
            print("CMD:", " ".join(cmd))
            rc, elapsed = _run_scraper(cmd, cwd=backend_dir)
            m = _collect_metrics(conn, limit=max(1, int(args.limit)))
            row = ProbeMetrics(
                run=i,
                return_code=rc,
                elapsed_sec=round(elapsed, 2),
                **m,
            )
            results.append(row)
            print(json.dumps(asdict(row), ensure_ascii=False))
    finally:
        conn.close()

    print("\n=== Summary ===")
    print(json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


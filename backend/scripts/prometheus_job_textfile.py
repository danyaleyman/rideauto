#!/usr/bin/env python3
"""Запись метрик последнего запуска batch/cron job для node_exporter textfile collector.

Переменные окружения:
  WRA_JOB_METRICS_TEXTFILE — путь к *.prom (например /var/lib/node_exporter/textfile_collector/catalog_sync.prom)
  JOB_NAME — имя задачи (по умолчанию catalog_job)
  EXIT_CODE — код выхода (0 успех)
  DURATION_SEC — длительность в секундах

Пример обёртки:
  start=$(date +%s)
  python postgres_catalog_sync.py ... || ec=$?
  export EXIT_CODE=${ec:-0}
  export DURATION_SEC=$(echo "$(date +%s)-$start" | bc)
  export JOB_NAME=wra_postgres_catalog_sync
  python scripts/prometheus_job_textfile.py
"""
from __future__ import annotations

import os
import time
from pathlib import Path


def main() -> None:
    path = (os.environ.get("WRA_JOB_METRICS_TEXTFILE") or "").strip()
    if not path:
        return
    job = (os.environ.get("JOB_NAME") or "catalog_job").strip() or "catalog_job"
    job_safe = job.replace("\\", "").replace('"', "")[:64]
    try:
        exit_code = int(float(os.environ.get("EXIT_CODE", "0")))
    except ValueError:
        exit_code = -1
    try:
        duration = float(os.environ.get("DURATION_SEC", "0"))
    except ValueError:
        duration = 0.0
    now = int(time.time())
    lines = [
        "# HELP wra_job_last_completion_unixtime Unix time of last job completion.",
        "# TYPE wra_job_last_completion_unixtime gauge",
        f'wra_job_last_completion_unixtime{{job="{job_safe}"}} {now}',
        "# HELP wra_job_last_exit_code Exit code of last job run (0 = success).",
        "# TYPE wra_job_last_exit_code gauge",
        f'wra_job_last_exit_code{{job="{job_safe}"}} {exit_code}',
        "# HELP wra_job_last_duration_seconds Wall duration of last job run in seconds.",
        "# TYPE wra_job_last_duration_seconds gauge",
        f'wra_job_last_duration_seconds{{job="{job_safe}"}} {duration}',
        "",
    ]
    text = "\n".join(lines)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(p)


if __name__ == "__main__":
    main()

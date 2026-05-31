"""Чистые построители удалённых shell-команд (без побочных эффектов → легко тестировать).

Все значения, попадающие в shell, экранируются через shlex.quote (POSIX-сервер).
Секреты сюда НЕ передаются: meili-sync читает WRA_* из окружения контейнера в рантайме.
"""
from __future__ import annotations

import shlex
from typing import Iterable, Optional

DEFAULT_REMOTE_ROOT = "/opt/rideauto"
MIGRATE_SCRIPT = "/app/infrastructure/postgresql/migrate.py"
MEILI_SYNC_SCRIPT = "/app/infrastructure/meilisearch/sync_meilisearch.py"


def in_root(remote_root: str, cmd: str) -> str:
    """Выполнить cmd в каталоге проекта."""
    return f"cd {shlex.quote(remote_root)} && {cmd}"


def compose(args: Iterable[str]) -> str:
    """docker compose <args...> с экранированием."""
    parts = " ".join(shlex.quote(a) for a in args)
    return f"docker compose {parts}".rstrip()


def api_exec(inner: str, env: Optional[dict[str, str]] = None) -> str:
    """docker compose exec -T [ -e K=V ... ] api sh -lc '<inner>'."""
    env_flags = ""
    if env:
        env_flags = " " + " ".join(f"-e {shlex.quote(f'{k}={v}')}" for k, v in env.items())
    return f"docker compose exec -T{env_flags} api sh -lc {shlex.quote(inner)}"


def postgres_exec(sql: str, user: str = "wra", db: str = "wra") -> str:
    """Выполнить SQL внутри контейнера postgres (без psql на хосте)."""
    inner = f"psql -v ON_ERROR_STOP=1 -U {shlex.quote(user)} -d {shlex.quote(db)} -c {shlex.quote(sql)}"
    return f"docker compose exec -T postgres {inner}"


def migrate(action: str = "status") -> str:
    """Раннер миграций внутри контейнера api (DSN берётся из WRA_PG_DSN контейнера)."""
    if action not in {"status", "apply", "check", "baseline"}:
        raise ValueError(f"unknown migrate action: {action!r}")
    return api_exec(f"python {MIGRATE_SCRIPT} {action}")


def meili_sync(preflight_gate: bool = False, extra_args: Optional[list[str]] = None) -> str:
    """Синхронизация Meilisearch. Секреты (WRA_MEILISEARCH_KEY/URL, WRA_PG_DSN)
    подставляются shell'ом ИЗ ОКРУЖЕНИЯ КОНТЕЙНЕРА — не из нашего кода."""
    extra = (" " + " ".join(shlex.quote(a) for a in extra_args)) if extra_args else ""
    inner = (
        f"python {MEILI_SYNC_SCRIPT} "
        '--pg-dsn "$WRA_PG_DSN" '
        '--meili-url "$WRA_MEILISEARCH_URL" '
        '--meili-key "$WRA_MEILISEARCH_KEY"'
        f"{extra}"
    )
    gate = "1" if preflight_gate else "0"
    return api_exec(inner, env={"WRA_MEILI_PREFLIGHT_GATE": gate})


def rebuild_web() -> str:
    """Пересборка и перезапуск только сервиса web."""
    return "docker compose build web && docker compose up -d --no-deps web && docker compose ps web"


def tail_file(path: str, lines: int = 40) -> str:
    return f"tail -n {int(lines)} {shlex.quote(path)} 2>/dev/null || true"


def git_pull() -> str:
    return "git pull --ff-only 2>&1 || true"

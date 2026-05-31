"""Тесты deploy/ops: чистые билдеры команд + парсинг конфига (без SSH/секретов)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_OPS_DIR = _REPO_ROOT / "deploy" / "ops"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, _OPS_DIR / filename)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


commands = _load("rideauto_ops_commands", "commands.py")
config = _load("rideauto_ops_config", "config.py")


# --- commands ----------------------------------------------------------------


def test_in_root_quotes_path() -> None:
    assert commands.in_root("/opt/ride auto", "ls") == "cd '/opt/ride auto' && ls"


def test_compose_quotes_args() -> None:
    assert commands.compose(["logs", "--tail", "50", "api"]) == "docker compose logs --tail 50 api"


def test_api_exec_wraps_and_quotes() -> None:
    out = commands.api_exec("python x.py")
    assert out == "docker compose exec -T api sh -lc 'python x.py'"


def test_api_exec_env_flags() -> None:
    out = commands.api_exec("echo hi", env={"WRA_MEILI_PREFLIGHT_GATE": "0"})
    assert "-e WRA_MEILI_PREFLIGHT_GATE=0" in out
    assert out.endswith("api sh -lc 'echo hi'")


def test_postgres_exec_quotes_sql() -> None:
    out = commands.postgres_exec("SELECT 1")
    assert "docker compose exec -T postgres psql" in out
    assert "-c 'SELECT 1'" in out


def test_migrate_valid_and_invalid() -> None:
    assert commands.MIGRATE_SCRIPT in commands.migrate("apply")
    with pytest.raises(ValueError):
        commands.migrate("nuke")


def test_meili_sync_uses_env_not_hardcoded_secret() -> None:
    out = commands.meili_sync(preflight_gate=True)
    # секреты подставляются shell'ом из окружения контейнера
    assert '"$WRA_MEILISEARCH_KEY"' in out
    assert '"$WRA_PG_DSN"' in out
    assert "WRA_MEILI_PREFLIGHT_GATE=1" in out
    # никаких реальных ключей в команде
    assert "rideauto_meili" not in out
    assert "wra:wra@" not in out


# --- config ------------------------------------------------------------------


def test_load_env_file_parsing(tmp_path: Path) -> None:
    p = tmp_path / ".env.deploy"
    p.write_text(
        "\n".join(
            [
                "# comment",
                "RIDEAUTO_DEPLOY_HOST=10.0.0.1",
                'RIDEAUTO_DEPLOY_USER="root"',
                "export RIDEAUTO_DEPLOY_PORT=2222",
                "EMPTY=",
                "bad line without equals",
            ]
        ),
        encoding="utf-8",
    )
    parsed = config.load_env_file(p)
    assert parsed["RIDEAUTO_DEPLOY_HOST"] == "10.0.0.1"
    assert parsed["RIDEAUTO_DEPLOY_USER"] == "root"
    assert parsed["RIDEAUTO_DEPLOY_PORT"] == "2222"


def test_from_env_requires_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RIDEAUTO_DEPLOY_HOST", raising=False)
    with pytest.raises(SystemExit, match="RIDEAUTO_DEPLOY_HOST"):
        config.RemoteConfig.from_env(env_file={})


def test_from_env_requires_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RIDEAUTO_DEPLOY_SSH_PASSWORD", raising=False)
    monkeypatch.delenv("RIDEAUTO_DEPLOY_SSH_KEY", raising=False)
    with pytest.raises(SystemExit, match="SSH_PASSWORD or RIDEAUTO_DEPLOY_SSH_KEY"):
        config.RemoteConfig.from_env(env_file={"RIDEAUTO_DEPLOY_HOST": "10.0.0.1"})


def test_from_env_full_and_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in (
        "RIDEAUTO_DEPLOY_HOST",
        "RIDEAUTO_DEPLOY_USER",
        "RIDEAUTO_DEPLOY_PORT",
        "RIDEAUTO_DEPLOY_SSH_PASSWORD",
        "RIDEAUTO_DEPLOY_SSH_KEY",
        "RIDEAUTO_DEPLOY_REMOTE_ROOT",
    ):
        monkeypatch.delenv(k, raising=False)
    cfg = config.RemoteConfig.from_env(
        env_file={
            "RIDEAUTO_DEPLOY_HOST": "10.0.0.1",
            "RIDEAUTO_DEPLOY_SSH_PASSWORD": "supersecret",
        }
    )
    assert cfg.host == "10.0.0.1"
    assert cfg.user == "root"
    assert cfg.port == 22
    assert cfg.remote_root == "/opt/rideauto"
    red = cfg.redacted()
    assert "supersecret" not in red
    assert "auth=password" in red

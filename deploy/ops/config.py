"""Конфигурация SSH-подключения к серверу RideAuto из окружения.

Приоритет источников: реальные переменные окружения > deploy/.env.deploy (gitignored).
В исходниках НЕТ ни хоста, ни логина, ни паролей/ключей.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

ENV_FILE_NAME = ".env.deploy"


def _deploy_env_path() -> Path:
    # deploy/ops/config.py -> deploy/.env.deploy
    return Path(__file__).resolve().parents[1] / ENV_FILE_NAME


def load_env_file(path: Optional[Path] = None) -> dict[str, str]:
    """Минимальный парсер dotenv (KEY=VALUE, поддержка # и кавычек). Без внешних зависимостей."""
    p = path or _deploy_env_path()
    out: dict[str, str] = {}
    if not p.is_file():
        return out
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if key.lower().startswith("export "):
            key = key[len("export "):].strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in {'"', "'"}:
            val = val[1:-1]
        if key:
            out[key] = val
    return out


def _get(env_file: dict[str, str], name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.environ.get(name)
    if v is not None and v.strip() != "":
        return v
    fv = env_file.get(name)
    if fv is not None and fv.strip() != "":
        return fv
    return default


@dataclass(frozen=True)
class RemoteConfig:
    host: str
    user: str
    port: int
    remote_root: str
    password: Optional[str]
    key_filename: Optional[str]
    connect_timeout: int

    @classmethod
    def from_env(cls, env_file: Optional[dict[str, str]] = None) -> "RemoteConfig":
        ef = env_file if env_file is not None else load_env_file()
        host = _get(ef, "RIDEAUTO_DEPLOY_HOST")
        if not host:
            raise SystemExit(
                "RIDEAUTO_DEPLOY_HOST is required (set env var or deploy/.env.deploy). "
                "See deploy/ops/README.md"
            )
        password = _get(ef, "RIDEAUTO_DEPLOY_SSH_PASSWORD")
        key_filename = _get(ef, "RIDEAUTO_DEPLOY_SSH_KEY")
        if not password and not key_filename:
            raise SystemExit(
                "provide RIDEAUTO_DEPLOY_SSH_PASSWORD or RIDEAUTO_DEPLOY_SSH_KEY"
            )
        return cls(
            host=host,
            user=_get(ef, "RIDEAUTO_DEPLOY_USER", "root") or "root",
            port=int(_get(ef, "RIDEAUTO_DEPLOY_PORT", "22") or "22"),
            remote_root=_get(ef, "RIDEAUTO_DEPLOY_REMOTE_ROOT", "/opt/rideauto") or "/opt/rideauto",
            password=password,
            key_filename=key_filename,
            connect_timeout=int(_get(ef, "RIDEAUTO_DEPLOY_CONNECT_TIMEOUT", "30") or "30"),
        )

    def redacted(self) -> str:
        auth = "key" if self.key_filename else "password"
        return f"{self.user}@{self.host}:{self.port} root={self.remote_root} auth={auth}"

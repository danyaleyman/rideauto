"""Тонкая обёртка над paramiko: подключение из RemoteConfig, run/put, контекст-менеджер."""
from __future__ import annotations

import sys
from dataclasses import dataclass

from .config import RemoteConfig


@dataclass
class RunResult:
    exit_code: int
    stdout: str
    stderr: str


class RemoteSession:
    def __init__(self, config: RemoteConfig) -> None:
        self.config = config
        self._client = None

    def __enter__(self) -> "RemoteSession":
        self.connect()
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def connect(self) -> None:
        try:
            import paramiko  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise SystemExit(
                "paramiko is required: pip install -r deploy/requirements-deploy.txt"
            ) from exc
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        kwargs: dict[str, object] = {
            "hostname": self.config.host,
            "port": self.config.port,
            "username": self.config.user,
            "timeout": self.config.connect_timeout,
        }
        if self.config.key_filename:
            kwargs["key_filename"] = self.config.key_filename
        if self.config.password:
            kwargs["password"] = self.config.password
        c.connect(**kwargs)  # type: ignore[arg-type]
        self._client = c

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def run(self, command: str, timeout: int = 600, stream: bool = True) -> RunResult:
        if self._client is None:
            raise RuntimeError("session is not connected")
        _, stdout, stderr = self._client.exec_command(command, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        code = stdout.channel.recv_exit_status()
        if stream:
            _safe_print(out)
            if err.strip():
                _safe_print("stderr: " + err[-4000:], file=sys.stderr)
        return RunResult(exit_code=code, stdout=out, stderr=err)

    def run_in_root(self, command: str, **kw) -> RunResult:
        from .commands import in_root

        return self.run(in_root(self.config.remote_root, command), **kw)

    def put(self, local_path: str, remote_path: str) -> None:
        if self._client is None:
            raise RuntimeError("session is not connected")
        sftp = self._client.open_sftp()
        try:
            sftp.put(local_path, remote_path)
        finally:
            sftp.close()


def _safe_print(text: str, file=sys.stdout) -> None:
    enc = getattr(file, "encoding", None) or "utf-8"
    file.write(text.encode(enc, errors="replace").decode(enc, errors="replace"))
    if not text.endswith("\n"):
        file.write("\n")
    file.flush()

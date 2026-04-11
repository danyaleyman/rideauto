"""load_config: overlay scraper_config.local.yaml."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from encar_scraper import load_config


def test_load_config_merges_local_overlay(tmp_path: Path) -> None:
    base = tmp_path / "scraper_config.yaml"
    base.write_text(
        textwrap.dedent(
            """
            max_new_saves_per_run: 5
            daily_update:
              new_cars_limit: 1
              sold_check_sample: 100
            storage:
              postgres:
                dsn: ""
            http:
              concurrency: 12
            """
        ).strip(),
        encoding="utf-8",
    )
    local = tmp_path / "scraper_config.local.yaml"
    local.write_text(
        textwrap.dedent(
            """
            max_new_saves_per_run: 0
            daily_update:
              sold_check_sample: 0
            http:
              concurrency: 3
            """
        ).strip(),
        encoding="utf-8",
    )

    cfg = load_config(str(base))
    assert cfg["max_new_saves_per_run"] == 0
    assert cfg["daily_update"]["new_cars_limit"] == 1
    assert cfg["daily_update"]["sold_check_sample"] == 0
    assert cfg["http"]["concurrency"] == 3
    assert cfg["storage"]["postgres"]["dsn"] == ""


def test_load_config_without_local(tmp_path: Path) -> None:
    base = tmp_path / "scraper_config.yaml"
    base.write_text(yaml.dump({"a": 1}), encoding="utf-8")
    cfg = load_config(str(base))
    assert cfg["a"] == 1


def test_load_config_extends_base(tmp_path: Path) -> None:
    base = tmp_path / "scraper_config.yaml"
    base.write_text(
        yaml.dump({"x": 1, "http": {"concurrency": 12}, "daily_update": {"sold_check_sample": 100}}),
        encoding="utf-8",
    )
    smoke = tmp_path / "smoke.yaml"
    smoke.write_text(
        textwrap.dedent(
            """
            extends: scraper_config.yaml
            http:
              concurrency: 2
            daily_update:
              sold_check_sample: 5
            """
        ).strip(),
        encoding="utf-8",
    )
    cfg = load_config(str(smoke))
    assert cfg["x"] == 1
    assert cfg["http"]["concurrency"] == 2
    assert cfg["daily_update"]["sold_check_sample"] == 5

"""Граф зависимостей стека RideAuto (снизу вверх — порядок диагностики и починки)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Component:
    id: str
    label: str
    depends_on: tuple[str, ...]
    """Имя сервиса в docker compose (None = не в compose)."""
    compose_service: Optional[str] = None


# Порядок важен: сначала чиним «фундамент», потом зависимые сервисы.
STACK: tuple[Component, ...] = (
    Component("postgres", "PostgreSQL", (), "postgres"),
    Component("redis", "Redis", ("postgres",), "redis"),
    Component("meilisearch", "Meilisearch", ("postgres",), "meilisearch"),
    Component("api", "FastAPI API", ("postgres", "redis", "meilisearch"), "api"),
    Component("web", "Next.js", ("api",), "web"),
    Component("edge", "HTTP edge (nginx → web/api)", ("web", "api"), None),
)


def topo_order() -> list[Component]:
    return list(STACK)


def component_by_id(cid: str) -> Optional[Component]:
    for c in STACK:
        if c.id == cid:
            return c
    return None


def find_root_cause(failed_ids: set[str]) -> list[str]:
    """
    Вернуть упорядоченный список компонентов для remediation (снизу вверх).
    Первый в списке — наиболее вероятная корневая причина.
    """
    order = topo_order()
    roots: list[str] = []
    for comp in order:
        if comp.id not in failed_ids:
            continue
        # Корень: упал сам, зависимости ниже по стеку — здоровы
        dep_failed = any(d in failed_ids for d in comp.depends_on)
        if not dep_failed:
            roots.append(comp.id)
    # Уникальные, сохраняя порядок
    seen: set[str] = set()
    out: list[str] = []
    for cid in roots:
        if cid not in seen:
            seen.add(cid)
            out.append(cid)
    return out

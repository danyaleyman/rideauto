"""Runtime parser stats for Che168 pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class Che168Stats:
    enabled: bool = True
    photos_downloaded: int = 0
    photos_failed: int = 0
    cars_with_spec: int = 0

    def add_photos(self, *, downloaded: int, failed: int) -> None:
        if not self.enabled:
            return
        self.photos_downloaded += max(0, int(downloaded or 0))
        self.photos_failed += max(0, int(failed or 0))

    def mark_with_spec(self) -> None:
        if not self.enabled:
            return
        self.cars_with_spec += 1

    def snapshot(self) -> Dict[str, int]:
        return {
            "photos_downloaded": int(self.photos_downloaded),
            "photos_failed": int(self.photos_failed),
            "cars_with_spec": int(self.cars_with_spec),
        }

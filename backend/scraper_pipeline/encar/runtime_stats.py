from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class EncarStats:
    enabled: bool = True
    cars_parsed_ok: int = 0
    cars_with_images: int = 0
    cars_with_images_fallback: int = 0
    cars_with_user_info: int = 0

    def mark_parsed_ok(self) -> None:
        if not self.enabled:
            return
        self.cars_parsed_ok += 1

    def mark_with_images(self, *, fallback: bool) -> None:
        if not self.enabled:
            return
        self.cars_with_images += 1
        if fallback:
            self.cars_with_images_fallback += 1

    def mark_with_user_info(self) -> None:
        if not self.enabled:
            return
        self.cars_with_user_info += 1

    def snapshot(self) -> Dict[str, int]:
        return {
            "cars_parsed_ok": int(self.cars_parsed_ok),
            "cars_with_images": int(self.cars_with_images),
            "cars_with_images_fallback": int(self.cars_with_images_fallback),
            "cars_with_user_info": int(self.cars_with_user_info),
        }

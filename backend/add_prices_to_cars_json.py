#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Добавляет рассчитанные цены (калькулятор растаможки, KRW→USDT→RUB, брокер, 10%)
в существующий cars.json. Не требует SQLite — читает и перезаписывает cars.json.
Запуск: python add_prices_to_cars_json.py [путь к cars.json]
После запуска обновите страницу в браузере — цены появятся в карточках и в «Подробный расчёт».
"""
import json
import sys
from pathlib import Path


def main():
    default_path = (Path(__file__).resolve().parent.parent / "frontend" / "cars.json")
    path = Path(sys.argv[1] if len(sys.argv) > 1 else default_path)
    if not path.exists():
        print(f"Файл не найден: {path}", file=sys.stderr)
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    cars = data.get("result") or []
    if not cars:
        print("В файле нет массива result с авто. Ничего не делаем.")
        return

    try:
        from price import PriceCalculator
    except ImportError:
        print("Ошибка: не найден модуль price. Запустите скрипт из папки проекта.", file=sys.stderr)
        sys.exit(1)

    calc = PriceCalculator()
    ok, fail = 0, 0
    for i, car in enumerate(cars):
        obj = car.get("data")
        if obj is None:
            obj = car
        try:
            calc.update_car_with_prices(obj)
            if isinstance(obj, dict):
                obj.pop("price_calc_failed", None)
            if car.get("data") is not obj:
                car["data"] = obj
            ok += 1
        except Exception as e:
            if i == 0:
                print(f"Предупреждение при расчёте первого авто: {e}", file=sys.stderr)
            if isinstance(obj, dict):
                obj["price_calc_failed"] = True
            if car.get("data") is not obj:
                car["data"] = obj
            fail += 1

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Готово: {path}")
    print(f"  Рассчитано: {ok}, без цены (ошибка/нет данных): {fail}")
    print("  Обновите страницу в браузере — цены появятся в каталоге и в «Подробный расчёт».")


if __name__ == "__main__":
    main()

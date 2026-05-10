#!/usr/bin/env python3
"""
Диагностика парсера Che168 — проверяем, почему не вытягиваются характеристики
"""

import asyncio
import json
import sys
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, '/opt/rideauto')

from scraper_pipeline.che168.client import AsyncChe168Client
from scraper_pipeline.che168.parser import (
    parse_one_che168_car_async,
    che168_carinfo_body,
    merge_che168_api_carinfo_envelope,
)
from scraper_pipeline.encar.savers import build_car_saver
from scraper_pipeline.checkpoint_pg import CheckpointAsync

async def debug_car(car_id: str):
    """Диагностика одного авто"""
    print(f"\n{'='*60}")
    print(f"Диагностика авто: {car_id}")
    print(f"{'='*60}")
    
    # Загружаем конфиг
    from encar_scraper import load_config
    config = load_config("/opt/rideauto/che168_scraper.yaml")
    
    async with AsyncChe168Client(config, None) as client:
        # 1. Получаем сырой ответ API
        print("\n1. Запрос /carinfo...")
        raw_info, status, err = await client.fetch_carinfo(car_id)
        print(f"   Статус: {status}, Ошибка: {err}")
        
        if status != 200:
            print(f"   ❌ Ошибка API")
            return
        
        # 2. Проверяем specid в сыром ответе
        print("\n2. Проверка specid в сыром ответе:")
        specid_raw = None
        if isinstance(raw_info, dict):
            result = raw_info.get("result", {})
            specid_raw = result.get("specid") or result.get("specId")
            print(f"   raw_info['result']['specid'] = {specid_raw}")
        
        # 3. Применяем нормализацию
        print("\n3. После merge_che168_api_carinfo_envelope:")
        merged = merge_che168_api_carinfo_envelope(raw_info)
        specid_merged = merged.get("specid") or merged.get("specId")
        print(f"   specid после merge = {specid_merged}")
        print(f"   Ключи merged (первые 20): {list(merged.keys())[:20]}")
        
        # 4. Получаем ci_body
        print("\n4. После che168_carinfo_body:")
        ci_body = che168_carinfo_body(raw_info)
        specid_body = ci_body.get("specid") or ci_body.get("specId")
        print(f"   specid после carinfo_body = {specid_body}")
        
        # 5. Если specid есть — запрашиваем specparam
        if specid_body:
            print(f"\n5. Запрос /specparam?specid={specid_body}...")
            specparam, st_sp, err_sp = await client.fetch_specparam(specid_body)
            if st_sp == 200 and specparam:
                print(f"   ✅ /specparam успешно получен")
                # Показываем ключи
                result_sp = specparam.get("result", {}) if isinstance(specparam, dict) else {}
                print(f"   Ключи specparam: {list(result_sp.keys())[:10]}")
                # Показываем значения
                print(f"   displacement: {result_sp.get('displacement')}")
                print(f"   maxpower: {result_sp.get('maxpower')}")
                print(f"   gearbox: {result_sp.get('gearbox')}")
                print(f"   drivemode: {result_sp.get('drivemode')}")
                print(f"   fueltype: {result_sp.get('fueltype')}")
            else:
                print(f"   ❌ /specparam ошибка: статус {st_sp}")
        else:
            print("\n5. ❌ specid не найден — пропускаем specparam")
        
        # 6. Проверяем specconfig
        if specid_body:
            print(f"\n6. Запрос /specconfig?specid={specid_body}...")
            specconfig, st_sc, err_sc = await client.fetch_specconfig(specid_body)
            if st_sc == 200 and specconfig:
                print(f"   ✅ /specconfig успешно получен")
            else:
                print(f"   ❌ /specconfig ошибка: статус {st_sc}")
        
        # 7. Полный парсинг
        print("\n7. Полный парсинг через parse_one_che168_car_async...")
        try:
            parsed = await parse_one_che168_car_async(
                external_id=str(car_id),
                list_item={},
                carinfo=raw_info,
                specparam=specparam if specid_body else None,
                specconfig=specconfig if specid_body else None,
                recommend=None,
                report_summary=None,
                assume_price_wan_yuan=False,
            )
            
            if parsed and isinstance(parsed, dict):
                data = parsed.get("data", {})
                print(f"\n8. Результат парсинга:")
                print(f"   power_hp: {data.get('power_hp')}")
                print(f"   displacement_cc: {data.get('displacement_cc')}")
                print(f"   engine_type: {data.get('engine_type')}")
                print(f"   transmission_type: {data.get('transmission_type')}")
                print(f"   drive_type: {data.get('drive_type')}")
                print(f"   body_type: {data.get('body_type')}")
                print(f"   che168_recommended_options: {len(data.get('che168_recommended_options') or [])} шт")
            else:
                print("   ❌ Парсинг вернул None")
        except Exception as e:
            print(f"   ❌ Ошибка парсинга: {e}")

if __name__ == "__main__":
    car_id = sys.argv[1] if len(sys.argv) > 1 else "57958683"
    asyncio.run(debug_car(car_id))
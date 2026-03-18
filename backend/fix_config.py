#!/usr/bin/env python3
import json

# Пересохраняем config.json с правильной кодировкой
with open('config.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

with open('config.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("✅ Конфигурация пересохранена с правильной кодировкой")
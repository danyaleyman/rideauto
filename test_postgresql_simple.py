#!/usr/bin/env python3
"""
Простое тестирование системы без PostgreSQL
"""

import sys
import os

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_dependencies():
    """Тестирование зависимостей"""
    print("🧪 Тестирование зависимостей...")
    
    try:
        import psycopg2
        print("✅ psycopg2 установлен")
    except ImportError:
        print("❌ psycopg2 не установлен")
        return False
    
    try:
        import requests
        print("✅ requests установлен")
    except ImportError:
        print("❌ requests не установлен")
        return False
    
    try:
        import pandas
        print("✅ pandas установлен")
    except ImportError:
        print("❌ pandas не установлен")
        return False
    
    return True

def test_config():
    """Тестирование конфигурации"""
    print("⚙️ Тестирование конфигурации...")
    
    try:
        import json
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        print("✅ Конфигурационный файл загружен")
        print(f"   Хост: {config['db_config']['host']}")
        print(f"   Порт: {config['db_config']['port']}")
        print(f"   База данных: {config['db_config']['database']}")
        print(f"   Пользователь: {config['db_config']['user']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка загрузки конфигурации: {e}")
        return False

def test_system_files():
    """Тестирование файлов системы"""
    print("📁 Тестирование файлов системы...")
    
    required_files = [
        'run_system.py',
        'postgresql_database.py',
        'auto_update.py',
        'quick_start.py',
        'parser_full.py'
    ]
    
    all_exist = True
    for file in required_files:
        if os.path.exists(file):
            print(f"✅ {file} - найден")
        else:
            print(f"❌ {file} - не найден")
            all_exist = False
    
    return all_exist

def main():
    """Основная функция тестирования"""
    print("🚀 Простое тестирование системы Encar")
    print("=" * 50)
    
    success = True
    
    # Тест зависимостей
    if not test_dependencies():
        success = False
    
    print()
    
    # Тест конфигурации
    if not test_config():
        success = False
    
    print()
    
    # Тест файлов системы
    if not test_system_files():
        success = False
    
    print()
    print("=" * 50)
    
    if success:
        print("🎉 Все тесты пройдены!")
        print("💡 Система готова к использованию (но требует PostgreSQL)")
        print("\n📝 Рекомендации:")
        print("   1. Установите PostgreSQL")
        print("   2. Создайте базу данных 'encar'")
        print("   3. Настройте пользователя и пароль")
        print("   4. Запустите: python quick_start.py")
    else:
        print("❌ Некоторые тесты не пройдены")
        print("💡 Проверьте зависимости и конфигурацию")
    
    return success

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
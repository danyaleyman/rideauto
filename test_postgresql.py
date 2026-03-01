#!/usr/bin/env python3
"""
Тестирование PostgreSQL базы данных
"""

import sys
import os
from datetime import datetime

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from postgresql_database import PostgreSQLDatabase


def test_postgresql_database():
    """Тестирование PostgreSQL базы данных"""
    print("🧪 Тестирование PostgreSQL базы данных...")
    
    try:
        # Создаем базу данных
        db = PostgreSQLDatabase(
            host="localhost",
            port=5432,
            database="encar",
            user="postgres",
            password="password"
        )
        
        print("✅ Подключение к PostgreSQL установлено")
        
        # Тестовые данные
        test_car = {
            'inner_id': 'test123',
            'data': {
                'mark': 'BMW',
                'model': 'X5',
                'price': '50000',
                'year': '2020',
                'vin': 'TESTVIN123456789',
                'color': 'Black',
                'mileage': '50000'
            },
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'last_seen': datetime.now().isoformat()
        }
        
        print("\n📝 Тестирование основных операций...")
        
        # 1. Добавление автомобиля
        result = db.add_or_update_car(test_car)
        print(f"✅ Добавление автомобиля: {'успешно' if result else 'не изменено'}")
        
        # 2. Повторное добавление без изменений
        result = db.add_or_update_car(test_car)
        print(f"✅ Повторное добавление без изменений: {'изменено' if result else 'не изменено'}")
        
        # 3. Обновление данных
        test_car['data']['price'] = '55000'
        result = db.add_or_update_car(test_car)
        print(f"✅ Обновление данных: {'успешно' if result else 'не изменено'}")
        
        # 4. Получение автомобиля
        car = db.get_car('test123')
        print(f"✅ Получение автомобиля: {'найден' if car else 'не найден'}")
        
        if car:
            print(f"   Марка: {car['data']['mark']}")
            print(f"   Модель: {car['data']['model']}")
            print(f"   Цена: {car['data']['price']}")
            print(f"   VIN: {car['data']['vin']}")
        
        print("\n🔍 Тестирование поиска и фильтрации...")
        
        # 5. Поиск по фильтрам
        filtered_cars = db.get_cars_by_filter({'mark': 'BMW', 'year': '2020'})
        print(f"✅ Поиск по фильтрам: найдено {len(filtered_cars)} автомобилей")
        
        # 6. Поиск по одному фильтру
        filtered_cars2 = db.get_cars_by_filter({'mark': 'BMW'})
        print(f"✅ Поиск по марке: найдено {len(filtered_cars2)} автомобилей")
        
        print("\n📊 Тестирование статистики...")
        
        # 7. Статистика
        stats = db.get_stats()
        print(f"✅ Статистика:")
        print(f"   Активных автомобилей: {stats['total_active']}")
        print(f"   Добавлено сегодня: {stats['added_today']}")
        print(f"   Обновлено сегодня: {stats['updated_today']}")
        print(f"   Удаленных: {stats['deleted_count']}")
        
        # 8. Расширенная статистика
        extended = stats['extended_stats']
        print(f"   Всего автомобилей: {extended['total_cars']}")
        print(f"   Активных: {extended['active_cars']}")
        print(f"   Неактивных: {extended['inactive_cars']}")
        print(f"   Добавлено за 24ч: {extended['added_last_24h']}")
        print(f"   Обновлено за 24ч: {extended['updated_last_24h']}")
        print(f"   Просмотрено за 24ч: {extended['seen_last_24h']}")
        
        print("\n⚡ Тестирование производительности...")
        
        # 9. Статистика производительности
        perf_stats = db.get_performance_stats()
        size_info = perf_stats['size_info']
        print(f"✅ Статистика производительности:")
        print(f"   Размер таблицы: {size_info.get('table_size', 'N/A')}")
        print(f"   Размер данных: {size_info.get('data_size', 'N/A')}")
        print(f"   Размер индексов: {size_info.get('index_size', 'N/A')}")
        
        # 10. Таблица статистики
        table_stats = perf_stats['table_stats']
        if table_stats:
            print(f"   Вставок: {table_stats.get('inserts', 0)}")
            print(f"   Обновлений: {table_stats.get('updates', 0)}")
            print(f"   Удалений: {table_stats.get('deletes', 0)}")
            print(f"   Live tuples: {table_stats.get('live_tuples', 0)}")
            print(f"   Dead tuples: {table_stats.get('dead_tuples', 0)}")
        
        print("\n🔄 Тестирование отслеживания изменений...")
        
        # 11. Тестирование отслеживания изменений
        test_car2 = {
            'inner_id': 'test456',
            'data': {
                'mark': 'Audi',
                'model': 'A4',
                'price': '40000',
                'year': '2019',
                'vin': 'AUDIVIN987654321'
            },
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'last_seen': datetime.now().isoformat()
        }
        
        # Добавляем второй автомобиль
        db.add_or_update_car(test_car2)
        
        # Получаем все ID
        all_ids = db.get_car_ids()
        print(f"✅ Получение всех ID: {len(all_ids)} автомобилей")
        
        # Помечаем один как неактивный
        inactive_count = db.mark_cars_as_inactive(['test123'])  # Оставляем только test123
        print(f"✅ Помечено неактивными: {inactive_count} автомобилей")
        
        # Проверяем статистику после пометки
        stats_after = db.get_stats()
        print(f"   Активных после пометки: {stats_after['total_active']}")
        
        print("\n🔎 Тестирование поиска дубликатов...")
        
        # 12. Поиск дубликатов
        duplicates = db.get_duplicate_cars()
        print(f"✅ Поиск дубликатов: найдено {len(duplicates)} групп дубликатов")
        
        if duplicates:
            for dup in duplicates:
                print(f"   VIN: {dup['vin']}, Количество: {dup['count']}")
        
        print("\n🧹 Тестирование очистки...")
        
        # 13. Очистка старых неактивных записей
        cleaned_count = db.cleanup_old_inactive_cars(days_to_keep=1)
        print(f"✅ Очистка старых записей: удалено {cleaned_count} записей")
        
        print("\n🎉 Все тесты PostgreSQL базы данных пройдены успешно!")
        print("\n💡 Рекомендации:")
        print("   - Регулярно запускайте VACUUM для поддержания производительности")
        print("   - Мониторьте размер базы данных")
        print("   - Настройте автоматическое резервное копирование")
        print("   - Используйте индексы для часто используемых полей")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования PostgreSQL: {e}")
        print("\n💡 Возможные решения:")
        print("   1. Убедитесь, что PostgreSQL сервер запущен")
        print("   2. Проверьте параметры подключения в config.json")
        print("   3. Убедитесь, что база данных 'encar' существует")
        print("   4. Проверьте права доступа пользователя")
        print("   5. Убедитесь, что установлен psycopg2-binary")
        return False


def test_performance():
    """Тестирование производительности"""
    print("\n⚡ Тестирование производительности...")
    
    try:
        db = PostgreSQLDatabase(
            host="localhost",
            port=5432,
            database="encar",
            user="postgres",
            password="password"
        )
        
        import time
        
        # Тест вставки 100 автомобилей
        print("📝 Тест вставки 100 автомобилей...")
        start_time = time.time()
        
        for i in range(100):
            test_car = {
                'inner_id': f'perf_test_{i}',
                'data': {
                    'mark': f'Mark{i % 10}',
                    'model': f'Model{i % 5}',
                    'price': str(20000 + i * 1000),
                    'year': str(2015 + i % 10),
                    'vin': f'PERF{i:09d}'
                },
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                'last_seen': datetime.now().isoformat()
            }
            db.add_or_update_car(test_car)
        
        insert_time = time.time() - start_time
        print(f"✅ Вставка 100 автомобилей: {insert_time:.2f} сек")
        
        # Тест поиска
        print("🔍 Тест поиска...")
        start_time = time.time()
        
        for i in range(10):
            cars = db.get_cars_by_filter({'mark': f'Mark{i}'}, limit=10)
        
        search_time = time.time() - start_time
        print(f"✅ Поиск по 10 маркам: {search_time:.2f} сек")
        
        # Тест получения всех автомобилей
        print("📋 Тест получения всех автомобилей...")
        start_time = time.time()
        
        all_cars = db.get_all_active_cars(limit=1000)
        
        get_all_time = time.time() - start_time
        print(f"✅ Получение 1000 автомобилей: {get_all_time:.2f} сек")
        
        print(f"\n📊 Производительность:")
        print(f"   Вставка: {100/insert_time:.1f} авто/сек")
        print(f"   Поиск: {10/search_time:.1f} запросов/сек")
        print(f"   Выборка: {1000/get_all_time:.1f} авто/сек")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования производительности: {e}")
        return False


if __name__ == '__main__':
    print("🚀 Запуск тестирования PostgreSQL системы Encar")
    print("=" * 60)
    
    # Основное тестирование
    success = test_postgresql_database()
    
    if success:
        # Тестирование производительности
        test_performance()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 Все тесты пройдены! Система готова к использованию.")
    else:
        print("❌ Тесты не пройдены. Проверьте конфигурацию.")
    
    sys.exit(0 if success else 1)
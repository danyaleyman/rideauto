#!/usr/bin/env python3
"""
Основной модуль системы Encar Parser
Содержит класс EncarSystem для управления парсингом и обновлением данных
"""

import sys
import os
import logging
import time
from typing import Dict, List, Optional, Any
from datetime import datetime

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from parser_full import EncarFullParser
from postgresql_database import PostgreSQLDatabase
from export_system import ExportSystem

logger = logging.getLogger(__name__)


class EncarSystem:
    """Основной класс системы парсинга Encar"""
    
    def __init__(self, db_config: Dict = None):
        """
        Инициализация системы парсинга
        
        Args:
            db_config: Конфигурация базы данных (если не используется внешняя база)
        """
        self.parser = EncarFullParser()
        self.db = PostgreSQLDatabase(**(db_config or {}))
        self.exporter = ExportSystem(self.db)
        
        logger.info("✅ EncarSystem инициализирован")
    
    def daily_update(self, max_workers: int = 5, max_cars: int = 1000) -> Dict[str, Any]:
        """
        Ежедневное обновление данных
        
        Args:
            max_workers: Количество потоков для парсинга
            max_cars: Максимальное количество автомобилей для обновления
            
        Returns:
            Статистика обновления
        """
        logger.info(f"🔄 Запуск ежедневного обновления ({max_cars} автомобилей, {max_workers} потоков)...")
        
        start_time = datetime.now()
        
        try:
            # Собираем данные
            cars = self.parser.collect_cars(
                max_cars_per_type=max_cars // 2,  # Половину на импортные, половину на отечественные
                delay=0.3,
                car_types=("for", "kor")
            )
            
            # Сохраняем в базу данных
            processed_count = 0
            successful_count = 0
            failed_count = 0
            
            for car in cars:
                processed_count += 1
                try:
                    # Проверяем, существует ли уже автомобиль в базе
                    existing_car = self.db.get_car_by_inner_id(car['data']['inner_id'])
                    
                    if existing_car:
                        # Обновляем существующий автомобиль
                        self.db.update_car(car['data'])
                        successful_count += 1
                        logger.debug(f"✅ Обновлен автомобиль {car['data']['inner_id']}")
                    else:
                        # Добавляем новый автомобиль
                        self.db.add_car(car['data'])
                        successful_count += 1
                        logger.debug(f"✅ Добавлен новый автомобиль {car['data']['inner_id']}")
                        
                except Exception as e:
                    failed_count += 1
                    logger.error(f"❌ Ошибка обработки автомобиля {car['data']['inner_id']}: {e}")
            
            # Обновляем статистику
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            result = {
                'total_processed': processed_count,
                'successful': successful_count,
                'failed': failed_count,
                'duration_seconds': duration,
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'update_type': 'daily'
            }
            
            logger.info(f"✅ Ежедневное обновление завершено: {result}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка ежедневного обновления: {e}")
            raise
    
    def full_scan(self, max_cars: int = 200000, max_workers: int = 5) -> Dict[str, Any]:
        """
        Полное сканирование всех доступных автомобилей
        
        Args:
            max_cars: Максимальное количество автомобилей для сканирования
            max_workers: Количество потоков для парсинга
            
        Returns:
            Статистика сканирования
        """
        logger.info(f"🔄 Запуск полного сканирования ({max_cars} автомобилей, {max_workers} потоков)...")
        
        start_time = datetime.now()
        
        try:
            # Собираем данные
            cars = self.parser.collect_cars(
                max_cars_per_type=max_cars // 2,  # Половину на импортные, половину на отечественные
                delay=0.3,
                car_types=("for", "kor")
            )
            
            # Сохраняем в базу данных
            processed_count = 0
            successful_count = 0
            failed_count = 0
            new_cars_count = 0
            
            for car in cars:
                processed_count += 1
                try:
                    # Проверяем, существует ли уже автомобиль в базе
                    existing_car = self.db.get_car_by_inner_id(car['data']['inner_id'])
                    
                    if existing_car:
                        # Обновляем существующий автомобиль
                        self.db.update_car(car['data'])
                        successful_count += 1
                        logger.debug(f"✅ Обновлен автомобиль {car['data']['inner_id']}")
                    else:
                        # Добавляем новый автомобиль
                        self.db.add_car(car['data'])
                        successful_count += 1
                        new_cars_count += 1
                        logger.debug(f"✅ Добавлен новый автомобиль {car['data']['inner_id']}")
                        
                except Exception as e:
                    failed_count += 1
                    logger.error(f"❌ Ошибка обработки автомобиля {car['data']['inner_id']}: {e}")
            
            # Обновляем статистику
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            result = {
                'total_processed': processed_count,
                'successful': successful_count,
                'failed': failed_count,
                'new_cars': new_cars_count,
                'duration_seconds': duration,
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'update_type': 'full'
            }
            
            logger.info(f"✅ Полное сканирование завершено: {result}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка полного сканирования: {e}")
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """Получает статистику по базе данных"""
        try:
            return self.db.get_stats()
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики: {e}")
            return {}
    
    def export_data(self, format_type: str = 'json', output_path: str = None) -> str:
        """
        Экспортирует данные в указанный формат
        
        Args:
            format_type: Формат экспорта (json, csv, excel)
            output_path: Путь для сохранения файла
            
        Returns:
            Путь к экспортированному файлу
        """
        try:
            if not output_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"encar_export_{timestamp}.{format_type}"
            
            return self.exporter.export_to_file(format_type, output_path)
            
        except Exception as e:
            logger.error(f"❌ Ошибка экспорта данных: {e}")
            raise
    
    def cleanup_old_data(self, days_to_keep: int = 30) -> Dict[str, Any]:
        """
        Очищает старые данные из базы данных
        
        Args:
            days_to_keep: Количество дней для хранения данных
            
        Returns:
            Статистика очистки
        """
        try:
            return self.db.cleanup_old_data(days_to_keep)
        except Exception as e:
            logger.error(f"❌ Ошибка очистки данных: {e}")
            raise
    
    def health_check(self) -> Dict[str, Any]:
        """Проверка состояния системы"""
        try:
            db_stats = self.db.get_stats()
            perf_stats = self.db.get_performance_stats()
            
            return {
                'status': 'healthy',
                'database_stats': db_stats,
                'performance_stats': perf_stats,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки состояния системы: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }


def main():
    """Тестовая функция для проверки системы"""
    print("🧪 Тестирование EncarSystem...")
    
    # Создаем систему
    system = EncarSystem()
    
    # Проверяем состояние системы
    health = system.health_check()
    print(f"🏥 Состояние системы: {health['status']}")
    
    if health['status'] == 'healthy':
        # Получаем статистику
        stats = system.get_stats()
        print(f"📊 Статистика базы данных: {stats}")
        
        print("✅ EncarSystem работает корректно!")
    else:
        print("❌ EncarSystem имеет проблемы!")
        print(f"Ошибка: {health.get('error', 'Неизвестная ошибка')}")


if __name__ == '__main__':
    main()
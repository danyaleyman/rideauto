#!/usr/bin/env python3
"""
Система экспорта данных Encar Parser
Предоставляет функции для экспорта данных из базы данных в различные форматы
"""

import json
import csv
import pandas as pd
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ExportSystem:
    """Система экспорта данных"""
    
    def __init__(self, db_connection):
        """
        Инициализация системы экспорта
        
        Args:
            db_connection: Подключение к базе данных
        """
        self.db = db_connection
        logger.info("✅ ExportSystem инициализирован")
    
    def export_to_json(self, output_path: str = None) -> str:
        """
        Экспортирует данные в JSON формат
        
        Args:
            output_path: Путь для сохранения файла
            
        Returns:
            Путь к экспортированному файлу
        """
        try:
            if not output_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"encar_export_{timestamp}.json"
            
            # Получаем данные из базы
            cars = self.db.get_all_cars()
            
            # Подготавливаем данные для экспорта
            export_data = []
            for car in cars:
                export_data.append({
                    'id': car.get('id'),
                    'inner_id': car.get('inner_id'),
                    'url': car.get('url'),
                    'mark': car.get('mark'),
                    'model': car.get('model'),
                    'generation': car.get('generation'),
                    'configuration': car.get('configuration'),
                    'complectation': car.get('complectation'),
                    'year': car.get('year'),
                    'color': car.get('color'),
                    'price': car.get('price'),
                    'price_won': car.get('price_won'),
                    'km_age': car.get('km_age'),
                    'engine_type': car.get('engine_type'),
                    'transmission_type': car.get('transmission_type'),
                    'body_type': car.get('body_type'),
                    'address': car.get('address'),
                    'seller_type': car.get('seller_type'),
                    'is_dealer': car.get('is_dealer'),
                    'section': car.get('section'),
                    'seller': car.get('seller'),
                    'salon_id': car.get('salon_id'),
                    'description': car.get('description'),
                    'displacement': car.get('displacement'),
                    'offer_created': car.get('offer_created'),
                    'manufacturerName': car.get('manufacturerName'),
                    'modelName': car.get('modelName'),
                    'gradeName': car.get('gradeName'),
                    'modelGroupName': car.get('modelGroupName'),
                    'yearMonth': car.get('yearMonth'),
                    'images': car.get('images'),
                    'advertisementType': car.get('advertisementType'),
                    'salesStatus': car.get('salesStatus'),
                    'created_at': car.get('created_at'),
                    'power': car.get('power'),
                    'options': car.get('options'),
                    'vin': car.get('vin'),
                    'seatColor': car.get('seatColor'),
                    'seatCount': car.get('seatCount'),
                    'prep_drive_type': car.get('prep_drive_type'),
                    'drive_type': car.get('drive_type'),
                    'is_awd': car.get('is_awd'),
                    'is_duplicate': car.get('is_duplicate')
                })
            
            # Сохраняем в JSON файл
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'export_date': datetime.now().isoformat(),
                    'total_cars': len(export_data),
                    'cars': export_data
                }, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ Данные экспортированы в JSON: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"❌ Ошибка экспорта в JSON: {e}")
            raise
    
    def export_to_csv(self, output_path: str = None) -> str:
        """
        Экспортирует данные в CSV формат
        
        Args:
            output_path: Путь для сохранения файла
            
        Returns:
            Путь к экспортированному файлу
        """
        try:
            if not output_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"encar_export_{timestamp}.csv"
            
            # Получаем данные из базы
            cars = self.db.get_all_cars()
            
            if not cars:
                logger.warning("⚠️ Нет данных для экспорта в CSV")
                return output_path
            
            # Подготавливаем данные для экспорта
            fieldnames = [
                'id', 'inner_id', 'url', 'mark', 'model', 'generation', 'configuration',
                'complectation', 'year', 'color', 'price', 'price_won', 'km_age',
                'engine_type', 'transmission_type', 'body_type', 'address', 'seller_type',
                'is_dealer', 'section', 'seller', 'salon_id', 'description', 'displacement',
                'offer_created', 'manufacturerName', 'modelName', 'gradeName', 'modelGroupName',
                'yearMonth', 'advertisementType', 'salesStatus', 'created_at', 'power',
                'vin', 'seatColor', 'seatCount', 'prep_drive_type', 'drive_type', 'is_awd', 'is_duplicate'
            ]
            
            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for car in cars:
                    row = {field: car.get(field, '') for field in fieldnames}
                    writer.writerow(row)
            
            logger.info(f"✅ Данные экспортированы в CSV: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"❌ Ошибка экспорта в CSV: {e}")
            raise
    
    def export_to_excel(self, output_path: str = None) -> str:
        """
        Экспортирует данные в Excel формат
        
        Args:
            output_path: Путь для сохранения файла
            
        Returns:
            Путь к экспортированному файлу
        """
        try:
            if not output_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"encar_export_{timestamp}.xlsx"
            
            # Получаем данные из базы
            cars = self.db.get_all_cars()
            
            if not cars:
                logger.warning("⚠️ Нет данных для экспорта в Excel")
                return output_path
            
            # Преобразуем в DataFrame
            df = pd.DataFrame(cars)
            
            # Сохраняем в Excel
            df.to_excel(output_path, index=False, engine='openpyxl')
            
            logger.info(f"✅ Данные экспортированы в Excel: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"❌ Ошибка экспорта в Excel: {e}")
            raise
    
    def export_to_file(self, format_type: str = 'json', output_path: str = None) -> str:
        """
        Экспортирует данные в указанный формат
        
        Args:
            format_type: Формат экспорта (json, csv, excel)
            output_path: Путь для сохранения файла
            
        Returns:
            Путь к экспортированному файлу
        """
        if format_type.lower() == 'json':
            return self.export_to_json(output_path)
        elif format_type.lower() == 'csv':
            return self.export_to_csv(output_path)
        elif format_type.lower() == 'excel':
            return self.export_to_excel(output_path)
        else:
            raise ValueError(f"❌ Неподдерживаемый формат экспорта: {format_type}")
    
    def export_filtered_data(self, filters: Dict[str, Any], format_type: str = 'json', 
                           output_path: str = None) -> str:
        """
        Экспортирует отфильтрованные данные
        
        Args:
            filters: Фильтры для данных
            format_type: Формат экспорта
            output_path: Путь для сохранения файла
            
        Returns:
            Путь к экспортированному файлу
        """
        try:
            if not output_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"encar_filtered_export_{timestamp}.{format_type}"
            
            # Получаем отфильтрованные данные из базы
            cars = self.db.get_cars_by_filters(filters)
            
            if format_type.lower() == 'json':
                return self._export_filtered_to_json(cars, output_path, filters)
            elif format_type.lower() == 'csv':
                return self._export_filtered_to_csv(cars, output_path)
            elif format_type.lower() == 'excel':
                return self._export_filtered_to_excel(cars, output_path)
            else:
                raise ValueError(f"❌ Неподдерживаемый формат экспорта: {format_type}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка экспорта отфильтрованных данных: {e}")
            raise
    
    def _export_filtered_to_json(
        self, cars: List[Dict], output_path: str, filters: Optional[Dict[str, Any]] = None
    ) -> str:
        """Экспорт отфильтрованных данных в JSON"""
        try:
            export_data = []
            for car in cars:
                export_data.append({
                    'id': car.get('id'),
                    'inner_id': car.get('inner_id'),
                    'url': car.get('url'),
                    'mark': car.get('mark'),
                    'model': car.get('model'),
                    'generation': car.get('generation'),
                    'configuration': car.get('configuration'),
                    'complectation': car.get('complectation'),
                    'year': car.get('year'),
                    'color': car.get('color'),
                    'price': car.get('price'),
                    'price_won': car.get('price_won'),
                    'km_age': car.get('km_age'),
                    'engine_type': car.get('engine_type'),
                    'transmission_type': car.get('transmission_type'),
                    'body_type': car.get('body_type'),
                    'address': car.get('address'),
                    'seller_type': car.get('seller_type'),
                    'is_dealer': car.get('is_dealer'),
                    'section': car.get('section'),
                    'seller': car.get('seller'),
                    'salon_id': car.get('salon_id'),
                    'description': car.get('description'),
                    'displacement': car.get('displacement'),
                    'offer_created': car.get('offer_created'),
                    'manufacturerName': car.get('manufacturerName'),
                    'modelName': car.get('modelName'),
                    'gradeName': car.get('gradeName'),
                    'modelGroupName': car.get('modelGroupName'),
                    'yearMonth': car.get('yearMonth'),
                    'images': car.get('images'),
                    'advertisementType': car.get('advertisementType'),
                    'salesStatus': car.get('salesStatus'),
                    'created_at': car.get('created_at'),
                    'power': car.get('power'),
                    'options': car.get('options'),
                    'vin': car.get('vin'),
                    'seatColor': car.get('seatColor'),
                    'seatCount': car.get('seatCount'),
                    'prep_drive_type': car.get('prep_drive_type'),
                    'drive_type': car.get('drive_type'),
                    'is_awd': car.get('is_awd'),
                    'is_duplicate': car.get('is_duplicate')
                })
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'export_date': datetime.now().isoformat(),
                    'total_cars': len(export_data),
                    'filters': filters or {},
                    'cars': export_data
                }, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ Отфильтрованные данные экспортированы в JSON: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"❌ Ошибка экспорта отфильтрованных данных в JSON: {e}")
            raise
    
    def _export_filtered_to_csv(self, cars: List[Dict], output_path: str) -> str:
        """Экспорт отфильтрованных данных в CSV"""
        try:
            if not cars:
                logger.warning("⚠️ Нет данных для экспорта в CSV")
                return output_path
            
            fieldnames = [
                'id', 'inner_id', 'url', 'mark', 'model', 'generation', 'configuration',
                'complectation', 'year', 'color', 'price', 'price_won', 'km_age',
                'engine_type', 'transmission_type', 'body_type', 'address', 'seller_type',
                'is_dealer', 'section', 'seller', 'salon_id', 'description', 'displacement',
                'offer_created', 'manufacturerName', 'modelName', 'gradeName', 'modelGroupName',
                'yearMonth', 'advertisementType', 'salesStatus', 'created_at', 'power',
                'vin', 'seatColor', 'seatCount', 'prep_drive_type', 'drive_type', 'is_awd', 'is_duplicate'
            ]
            
            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for car in cars:
                    row = {field: car.get(field, '') for field in fieldnames}
                    writer.writerow(row)
            
            logger.info(f"✅ Отфильтрованные данные экспортированы в CSV: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"❌ Ошибка экспорта отфильтрованных данных в CSV: {e}")
            raise
    
    def _export_filtered_to_excel(self, cars: List[Dict], output_path: str) -> str:
        """Экспорт отфильтрованных данных в Excel"""
        try:
            if not cars:
                logger.warning("⚠️ Нет данных для экспорта в Excel")
                return output_path
            
            df = pd.DataFrame(cars)
            df.to_excel(output_path, index=False, engine='openpyxl')
            
            logger.info(f"✅ Отфильтрованные данные экспортированы в Excel: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"❌ Ошибка экспорта отфильтрованных данных в Excel: {e}")
            raise


def main():
    """Тестовая функция для проверки системы экспорта"""
    print("🧪 Тестирование ExportSystem...")
    
    # Для тестирования нужно подключение к базе данных
    # Здесь просто создаем заглушку
    class MockDB:
        def get_all_cars(self):
            return [
                {
                    'id': 1,
                    'inner_id': 'test123',
                    'mark': 'Toyota',
                    'model': 'Camry',
                    'year': '2020',
                    'price': '25000'
                }
            ]
    
    db = MockDB()
    exporter = ExportSystem(db)
    
    try:
        # Тестируем экспорт в JSON
        json_path = exporter.export_to_json('test_export.json')
        print(f"✅ Экспорт в JSON успешен: {json_path}")
        
        # Тестируем экспорт в CSV
        csv_path = exporter.export_to_csv('test_export.csv')
        print(f"✅ Экспорт в CSV успешен: {csv_path}")
        
        print("✅ ExportSystem работает корректно!")
        
    except Exception as e:
        print(f"❌ Ошибка тестирования ExportSystem: {e}")


if __name__ == '__main__':
    main()
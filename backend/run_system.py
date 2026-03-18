#!/usr/bin/env python3
"""
Универсальный скрипт-обертка для запуска системы Encar Parser
Предоставляет простой интерфейс для всех операций системы
"""

import sys
import os
import argparse
import subprocess
import logging
from datetime import datetime
from pathlib import Path

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Пути проекта (repo root = parent of backend/)
BACKEND_DIR = Path(__file__).resolve().parent
REPO_DIR = BACKEND_DIR.parent

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(str(BACKEND_DIR / 'run_system.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class EncarSystemRunner:
    """Класс для управления запуском системы Encar"""
    
    def __init__(self):
        self.project_dir = BACKEND_DIR
        self.config_file = self.project_dir / 'config.json'
        
    def check_dependencies(self):
        """Проверка наличия зависимостей"""
        logger.info("🔍 Проверка зависимостей...")
        
        try:
            import psycopg2
            logger.info("✅ psycopg2 установлен")
        except ImportError:
            logger.error("❌ psycopg2 не установлен")
            return False
        
        try:
            import requests
            logger.info("✅ requests установлен")
        except ImportError:
            logger.error("❌ requests не установлен")
            return False
        
        try:
            import pandas
            logger.info("✅ pandas установлен")
        except ImportError:
            logger.error("❌ pandas не установлен")
            return False
        
        return True
    
    def install_dependencies(self):
        """Установка зависимостей"""
        logger.info("📦 Установка зависимостей...")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', str(self.project_dir / 'requirements.txt')])
            logger.info("✅ Зависимости установлены")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Ошибка установки зависимостей: {e}")
            return False
    
    def check_config(self):
        """Проверка наличия конфигурации"""
        if self.config_file.exists():
            logger.info("✅ Конфигурационный файл найден")
            return True
        else:
            logger.warning("⚠️  Конфигурационный файл не найден")
            return False
    
    def run_setup(self):
        """Запуск настройки системы"""
        logger.info("⚙️ Запуск настройки системы...")
        try:
            result = subprocess.run([sys.executable, str(self.project_dir / 'quick_start.py')], 
                                  check=True, capture_output=True, text=True)
            logger.info("✅ Настройка системы завершена")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Ошибка настройки системы: {e}")
            logger.error(f"Вывод: {e.stdout}")
            logger.error(f"Ошибки: {e.stderr}")
            return False
    
    def run_test(self):
        """Запуск тестирования системы"""
        logger.info("🧪 Запуск тестирования системы...")
        try:
            result = subprocess.run([sys.executable, str(self.project_dir / 'test_postgresql.py')], 
                                  check=True, capture_output=True, text=True)
            logger.info("✅ Тестирование системы завершено")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Ошибка тестирования системы: {e}")
            logger.error(f"Вывод: {e.stdout}")
            logger.error(f"Ошибки: {e.stderr}")
            return False
    
    def run_update(self, update_type='daily', workers=5):
        """Запуск обновления системы"""
        logger.info(f"🔄 Запуск {update_type} обновления ({workers} потоков)...")
        try:
            cmd = [sys.executable, str(self.project_dir / 'auto_update.py'), '--config', str(self.config_file), 
                   '--type', update_type, '--workers', str(workers)]
            
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info("✅ Обновление завершено")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Ошибка обновления: {e}")
            logger.error(f"Вывод: {e.stdout}")
            logger.error(f"Ошибки: {e.stderr}")
            return False
    
    def check_database_status(self):
        """Проверка статуса базы данных"""
        logger.info("🗄️ Проверка статуса базы данных...")
        
        try:
            # Проверяем наличие конфигурации
            if not self.check_config():
                logger.info("ℹ️  Конфигурационный файл не найден")
                return 'no_config'
            
            # Загружаем конфигурацию
            import json
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Пытаемся подключиться к базе данных
            from postgresql_database import PostgreSQLDatabase
            db = PostgreSQLDatabase(**config['db_config'])
            
            # Получаем статистику
            stats = db.get_stats()
            total_cars = stats.get('total_active', 0)
            
            # Проверяем дату последнего обновления
            last_scan = stats.get('last_full_scan', 'Never')
            
            logger.info(f"📊 Статус базы данных: {total_cars} активных автомобилей")
            logger.info(f"📅 Последнее полное сканирование: {last_scan}")
            
            # Определяем статус
            if total_cars == 0:
                return 'empty'
            elif last_scan == 'Never':
                return 'no_scan'
            else:
                # Проверяем давность последнего сканирования
                from datetime import datetime, timedelta
                try:
                    last_scan_date = datetime.fromisoformat(last_scan.replace('Z', '+00:00'))
                    days_diff = (datetime.now() - last_scan_date).days
                    
                    if days_diff > 7:
                        return 'old_scan'
                    elif days_diff > 1:
                        return 'stale_scan'
                    else:
                        return 'fresh'
                except:
                    return 'unknown_age'
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки базы данных: {e}")
            return 'error'
    
    def run_initial_data_load(self):
        """Запуск первоначальной загрузки данных"""
        logger.info("📥 Запуск первоначальной загрузки данных...")
        try:
            result = subprocess.run([sys.executable, str(self.project_dir / 'parser_full.py')], 
                                  check=True, capture_output=True, text=True)
            logger.info("✅ Первоначальная загрузка данных завершена")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Ошибка первоначальной загрузки данных: {e}")
            logger.error(f"Вывод: {e.stdout}")
            logger.error(f"Ошибки: {e.stderr}")
            return False
    
    def run_smart_update(self):
        """Умное обновление системы (автоматическое определение режима)"""
        logger.info("🧠 Запуск умного обновления...")
        
        # Проверка статуса базы данных
        db_status = self.check_database_status()
        
        if db_status == 'no_config':
            logger.error("❌ Конфигурационный файл не найден. Запустите --setup для настройки.")
            return False
        
        elif db_status == 'error':
            logger.error("❌ Ошибка подключения к базе данных. Проверьте конфигурацию.")
            return False
        
        elif db_status == 'empty':
            logger.info("📥 База данных пустая. Запуск первоначальной загрузки...")
            if not self.run_initial_data_load():
                return False
            # После загрузки данных запускаем тестирование
            if not self.run_test():
                return False
        
        elif db_status == 'no_scan':
            logger.info("🔄 База данных есть, но сканирование не проводилось. Запуск полного обновления...")
            if not self.run_update('full', 3):
                return False
        
        elif db_status == 'old_scan':
            logger.info("🔄 Данные устарели (>7 дней). Запуск полного обновления...")
            if not self.run_update('full', 5):
                return False
        
        elif db_status == 'stale_scan':
            logger.info("🔄 Данные немного устарели (>1 дня). Запуск ежедневного обновления...")
            if not self.run_update('daily', 5):
                return False
        
        elif db_status == 'fresh':
            logger.info("✅ Данные актуальны. Запуск ежедневного обновления...")
            if not self.run_update('daily', 5):
                return False
        
        elif db_status == 'unknown_age':
            logger.info("❓ Возраст данных неизвестен. Запуск ежедневного обновления...")
            if not self.run_update('daily', 5):
                return False
        
        logger.info("✅ Умное обновление завершено")
        return True
    
    def run_full_setup(self):
        """Полная настройка системы"""
        logger.info("🚀 Полная настройка системы...")
        
        # 1. Проверка и установка зависимостей
        if not self.check_dependencies():
            if not self.install_dependencies():
                return False
        
        # 2. Проверка конфигурации
        if not self.check_config():
            if not self.run_setup():
                return False
        
        # 3. Тестирование системы
        if not self.run_test():
            return False
        
        # 4. Проверка базы данных и умная загрузка данных
        db_status = self.check_database_status()
        if db_status in ['empty', 'no_scan']:
            logger.info("📥 Запуск первоначальной загрузки данных...")
            if not self.run_initial_data_load():
                return False
        
        logger.info("✅ Полная настройка завершена")
        return True
    
    def run_daily_update(self):
        """Запуск ежедневного обновления"""
        logger.info("📅 Запуск ежедневного обновления...")
        
        # Проверка конфигурации
        if not self.check_config():
            logger.error("❌ Конфигурационный файл не найден. Запустите --setup для настройки.")
            return False
        
        # Тестирование системы
        if not self.run_test():
            logger.error("❌ Тестирование системы не прошло. Проверьте конфигурацию.")
            return False
        
        # Запуск обновления
        return self.run_update('daily', 5)
    
    def run_full_scan(self):
        """Запуск полного сканирования"""
        logger.info("🔄 Запуск полного сканирования...")
        
        # Проверка конфигурации
        if not self.check_config():
            logger.error("❌ Конфигурационный файл не найден. Запустите --setup для настройки.")
            return False
        
        # Тестирование системы
        if not self.run_test():
            logger.error("❌ Тестирование системы не прошло. Проверьте конфигурацию.")
            return False
        
        # Запуск полного сканирования
        return self.run_update('full', 3)
    
    def setup_automation(self):
        """Настройка автоматического обновления"""
        logger.info("⏰ Настройка автоматического обновления...")
        
        import platform
        system = platform.system()
        
        try:
            if system in ['Linux', 'Darwin']:
                # Linux/macOS
                cron_path = self.project_dir / 'setup_cron.sh'
                result = subprocess.run(['chmod', '+x', str(cron_path)], check=True)
                result = subprocess.run([str(cron_path)], check=True, capture_output=True, text=True)
                logger.info("✅ Автоматическое обновление настроено для Linux/macOS")
            elif system == 'Windows':
                # Windows
                result = subprocess.run([str(REPO_DIR / 'setup_task_scheduler.bat')], check=True, capture_output=True, text=True)
                logger.info("✅ Автоматическое обновление настроено для Windows")
            else:
                logger.warning(f"⚠️  Автоматическая настройка не поддерживается для {system}")
                return False
            
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Ошибка настройки автоматического обновления: {e}")
            return False


def main():
    """Основная функция"""
    parser = argparse.ArgumentParser(description='Универсальный запуск системы Encar Parser')
    parser.add_argument('--setup', action='store_true', help='Только настройка системы')
    parser.add_argument('--test', action='store_true', help='Только тестирование системы')
    parser.add_argument('--daily', action='store_true', help='Ежедневное обновление')
    parser.add_argument('--full', action='store_true', help='Полный прогон')
    parser.add_argument('--smart', action='store_true', help='Умное обновление (автоопределение режима)')
    parser.add_argument('--auto', action='store_true', help='Настройка автоматического обновления')
    parser.add_argument('--workers', type=int, default=5, help='Количество потоков (по умолчанию: 5)')
    parser.add_argument('--quick', action='store_true', help='Быстрый запуск (только обновление)')
    
    args = parser.parse_args()
    
    runner = EncarSystemRunner()
    
    print("🚀 Encar Parser System Runner")
    print("=" * 50)
    print(f"Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    success = False
    
    try:
        # Определение режима запуска
        if args.setup:
            # Только настройка
            success = runner.run_full_setup()
            
        elif args.test:
            # Только тестирование
            success = runner.run_test()
            
        elif args.daily:
            # Ежедневное обновление
            success = runner.run_daily_update()
            
        elif args.full:
            # Полный прогон
            success = runner.run_full_scan()
            
        elif args.smart:
            # Умное обновление
            success = runner.run_smart_update()
            
        elif args.auto:
            # Настройка автоматического обновления
            success = runner.setup_automation()
            
        elif args.quick:
            # Быстрый запуск (только обновление)
            success = runner.run_daily_update()
            
        else:
            # Стандартный режим: проверка + обновление
            print("📋 Стандартный режим: проверка системы + умное обновление")
            success = runner.run_smart_update()
            
            # Проверка зависимостей
            if not runner.check_dependencies():
                print("📦 Установка зависимостей...")
                if not runner.install_dependencies():
                    success = False
                    return
            
            # Проверка конфигурации
            if not runner.check_config():
                print("⚙️ Настройка системы...")
                if not runner.run_setup():
                    success = False
                    return
            
            # Тестирование системы
            print("🧪 Тестирование системы...")
            if not runner.run_test():
                success = False
                return
            
            # Запуск обновления
            print("🔄 Запуск обновления...")
            success = runner.run_daily_update()
    
    except KeyboardInterrupt:
        print("\n❌ Запуск прерван пользователем")
        success = False
    
    except Exception as e:
        logger.error(f"❌ Непредвиденная ошибка: {e}")
        success = False
    
    finally:
        print("=" * 50)
        if success:
            print("🎉 Операция завершена успешно!")
        else:
            print("❌ Операция завершилась с ошибкой!")
            print("💡 Проверьте логи: run_system.log")
        print("=" * 50)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
#!/usr/bin/env python3
"""
Скрипт автоматического обновления данных Encar
Предназначен для запуска через cron (Linux/macOS) или Task Scheduler (Windows)
"""

import sys
import os
import logging
import smtplib
import subprocess
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional
from pathlib import Path

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main_system import EncarSystem
from postgresql_database import PostgreSQLDatabase

logger = logging.getLogger(__name__)


def _init_auto_update_logging() -> None:
    """Файл в logs/ от корня репо; при отказе в записи (www-data) — только stderr + journald."""
    repo_root = Path(__file__).resolve().parent.parent
    log_dir = repo_root / "logs"
    fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    handlers: List[logging.Handler] = [logging.StreamHandler()]
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_dir / "auto_update.log", encoding="utf-8"))
    except OSError as e:
        print(f"auto_update: cannot open logs/auto_update.log: {e}; logging to stderr only", file=sys.stderr)
    logging.basicConfig(level=logging.INFO, format=fmt, handlers=handlers, force=True)


class AutoUpdateManager:
    """Менеджер автоматического обновления"""
    
    def __init__(self, config: Dict = None):
        defaults = self._get_default_config()
        self.config = defaults
        if config and isinstance(config, dict):
            # Мягкое слияние, чтобы можно было передавать только часть настроек
            for k, v in config.items():
                if isinstance(v, dict) and isinstance(self.config.get(k), dict):
                    self.config[k].update(v)
                else:
                    self.config[k] = v
        self.system = None
        self.db = None
        
        # Настройка уведомлений
        self.smtp_config = self.config.get('smtp', {})
        self.notifications_enabled = bool(self.smtp_config.get('enabled', False))
        
        logger.info("=== Автоматическое обновление Encar запущено ===")
    
    def _get_default_config(self) -> Dict:
        """Получает конфигурацию по умолчанию"""
        return {
            'db_config': {
                'host': 'localhost',
                'port': 5432,
                'database': 'encar',
                'user': 'postgres',
                'password': 'password'
            },
            'update_config': {
                'max_workers': 5,
                'update_type': 'daily',  # 'daily' or 'full'
                'catalog_encar_nightly': True,
            },
            'notification_config': {
                'enabled': False,
                'smtp': {
                    'server': 'smtp.gmail.com',
                    'port': 587,
                    'username': 'your-email@gmail.com',
                    'password': 'your-app-password',
                    'to_email': 'admin@yourcompany.com'
                },
                'send_on_success': True,
                'send_on_error': True
            },
            'backup_config': {
                'enabled': True,
                'backup_dir': './backups',
                'keep_days': 7
            }
        }
    
    def setup_database(self):
        """Настраивает PostgreSQL базу данных"""
        try:
            db_cfg = self.config.get('db_config') or {}
            self.db = PostgreSQLDatabase(**db_cfg)
            logger.info("PostgreSQL база данных подключена")
            return True
        except Exception as e:
            logger.error(f"Ошибка подключения к PostgreSQL: {e}")
            # В окружениях без PostgreSQL продолжаем обновление без БД (экспорт в cars.json)
            self.db = None
            return False
    
    def setup_system(self):
        """Настраивает систему парсинга"""
        try:
            self.system = EncarSystem()
            if self.db is not None:
                # Заменяем базу данных на PostgreSQL
                self.system.db = self.db
                # Заменяем экспорт на PostgreSQL версию
                from export_system import ExportSystem
                self.system.exporter = ExportSystem(self.db)
            logger.info("Система парсинга настроена")
        except Exception as e:
            logger.error(f"Ошибка настройки системы: {e}")
            raise
    
    def run_daily_update(self) -> Dict:
        """Запускает ежедневное обновление"""
        logger.info("Запуск ежедневного обновления...")
        
        try:
            result = self.system.daily_update(
                max_workers=self.config['update_config']['max_workers']
            )
            
            logger.info(f"Ежедневное обновление завершено: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Ошибка ежедневного обновления: {e}")
            raise
    
    def run_full_scan(self) -> Dict:
        """Запускает полный скан"""
        logger.info("Запуск полного сканирования...")
        
        try:
            result = self.system.full_scan(
                max_cars=200000,
                max_workers=self.config['update_config']['max_workers']
            )
            
            logger.info(f"Полное сканирование завершено: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Ошибка полного сканирования: {e}")
            raise
    
    def create_backup(self) -> Optional[str]:
        """Создает резервную копию базы данных"""
        if not self.db:
            return None
        if not self.config['backup_config']['enabled']:
            return None
        
        try:
            backup_dir = self.config['backup_config']['backup_dir']
            os.makedirs(backup_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(backup_dir, f"encar_backup_{timestamp}.sql")
            
            # Создаем резервную копию с помощью pg_dump
            cmd = [
                'pg_dump',
                '-h', self.config['db_config']['host'],
                '-p', str(self.config['db_config']['port']),
                '-U', self.config['db_config']['user'],
                '-d', self.config['db_config']['database'],
                '-f', backup_file,
                '--verbose'
            ]
            
            # Устанавливаем переменную окружения для пароля
            env = os.environ.copy()
            env['PGPASSWORD'] = self.config['db_config']['password']
            
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"Резервная копия создана: {backup_file}")
                return backup_file
            else:
                logger.error(f"Ошибка создания резервной копии: {result.stderr}")
                return None
                
        except Exception as e:
            logger.error(f"Ошибка создания резервной копии: {e}")
            return None
    
    def cleanup_old_backups(self):
        """Удаляет старые резервные копии"""
        if not self.db:
            return
        if not self.config['backup_config']['enabled']:
            return
        
        try:
            backup_dir = self.config['backup_config']['backup_dir']
            keep_days = self.config['backup_config']['keep_days']
            
            if not os.path.exists(backup_dir):
                return
            
            current_time = datetime.now()
            cutoff_time = current_time.timestamp() - (keep_days * 24 * 60 * 60)
            
            removed_count = 0
            for filename in os.listdir(backup_dir):
                if filename.startswith('encar_backup_') and filename.endswith('.sql'):
                    filepath = os.path.join(backup_dir, filename)
                    if os.path.getctime(filepath) < cutoff_time:
                        os.remove(filepath)
                        removed_count += 1
            
            if removed_count > 0:
                logger.info(f"Удалено {removed_count} старых резервных копий")
                
        except Exception as e:
            logger.error(f"Ошибка очистки резервных копий: {e}")
    
    def send_notification(self, subject: str, body: str, is_error: bool = False):
        """Отправляет email уведомление"""
        if not self.notifications_enabled:
            return
        
        try:
            smtp_config = self.smtp_config
            
            if (is_error and not smtp_config.get('send_on_error', True)) or \
               (not is_error and not smtp_config.get('send_on_success', True)):
                return
            
            msg = MIMEMultipart()
            msg['From'] = smtp_config['username']
            msg['To'] = smtp_config['to_email']
            msg['Subject'] = f"[{'ERROR' if is_error else 'INFO'}] Encar Auto Update - {subject}"
            
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(smtp_config['server'], smtp_config['port'])
            server.starttls()
            server.login(smtp_config['username'], smtp_config['password'])
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Уведомление отправлено: {subject}")
            
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления: {e}")
    
    def get_system_health_check(self) -> Dict:
        """Проверяет состояние системы"""
        try:
            if not self.db:
                return {'status': 'warning', 'message': 'Database not connected'}
            
            stats = self.db.get_stats()
            perf_stats = self.db.get_performance_stats()
            
            return {
                'status': 'healthy',
                'database_stats': stats,
                'performance_stats': perf_stats,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Ошибка проверки состояния системы: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def run_update(self) -> Dict:
        """Запускает процесс обновления"""
        start_time = datetime.now()
        update_type = self.config['update_config']['update_type']
        backup_file = None
        
        try:
            # Настройка системы
            db_ok = self.setup_database()
            # Если PostgreSQL недоступен — обновление пропускается (Postgres-only каталог/чекпоинт).
            if not db_ok:
                logger.error("PostgreSQL недоступен — автообновление каталога Encar пропущено (нужен DB для чекпоинта и каталога).")
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                return {
                    "status": "error",
                    "update_type": update_type,
                    "duration_seconds": duration,
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "backup_file": None,
                    "result": {},
                    "health_check": {"status": "error", "message": "PostgreSQL not connected"},
                }

            self.setup_system()
            
            # Проверка состояния системы
            health_check = self.get_system_health_check()
            logger.info(f"Проверка состояния системы: {health_check['status']}")
            
            # Создание резервной копии
            backup_file = self.create_backup()
            
            # Запуск обновления
            if update_type == 'daily':
                result = self.run_daily_update()
            else:
                result = self.run_full_scan()
            
            # Очистка старых резервных копий
            self.cleanup_old_backups()
            
            # Подготовка отчета
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            report = {
                'status': 'success',
                'update_type': update_type,
                'duration_seconds': duration,
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'backup_file': backup_file,
                'result': result,
                'health_check': health_check
            }
            
            # Отправка уведомления об успехе
            if self.notifications_enabled:
                subject = f"Успешное {update_type} обновление"
                body = f"""
Обновление Encar завершено успешно!

Тип обновления: {update_type}
Длительность: {duration:.2f} секунд
Время начала: {start_time.strftime('%Y-%m-%d %H:%M:%S')}
Время окончания: {end_time.strftime('%Y-%m-%d %H:%M:%S')}

Результат:
- Обработано автомобилей: {result.get('total_processed', 0)}
- Успешно: {result.get('successful', 0)}
- Ошибки: {result.get('failed', 0)}

Статистика базы данных:
- Активных автомобилей: {health_check.get('database_stats', {}).get('total_active', 0)}
- Добавлено сегодня: {health_check.get('database_stats', {}).get('added_today', 0)}
- Обновлено сегодня: {health_check.get('database_stats', {}).get('updated_today', 0)}

Резервная копия: {'Создана' if backup_file else 'Не создана'}
                """
                
                self.send_notification(subject, body, is_error=False)
            
            logger.info("Автоматическое обновление завершено успешно!")

            uc = self.config.get("update_config") or {}
            if uc.get("catalog_encar_nightly", True):
                backend_dir = Path(__file__).resolve().parent
                repo_dir = backend_dir.parent
                config_path = repo_dir / "scraper_config.yaml"
                daily_update_path = backend_dir / "encar_daily_update.py"
                logger.info("Ночной цикл Encar (encar_daily_update --once): discover, sold, scraper…")
                proc_encar = subprocess.run(
                    [sys.executable, str(daily_update_path), "--once", "--config", str(config_path)],
                    cwd=str(repo_dir),
                )
                if proc_encar.returncode != 0:
                    raise RuntimeError(
                        f"encar_daily_update завершился с кодом {proc_encar.returncode}"
                    )
                report["catalog_encar_nightly"] = {"status": "ok", "returncode": 0}

            return report
            
        except Exception as e:
            # Отправка уведомления об ошибке
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            error_report = {
                'status': 'error',
                'update_type': update_type,
                'duration_seconds': duration,
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'error': str(e),
                'backup_file': backup_file
            }
            
            if self.notifications_enabled:
                subject = f"Ошибка {update_type} обновления"
                body = f"""
Обновление Encar завершилось с ошибкой!

Тип обновления: {update_type}
Длительность: {duration:.2f} секунд
Время начала: {start_time.strftime('%Y-%m-%d %H:%M:%S')}
Время окончания: {end_time.strftime('%Y-%m-%d %H:%M:%S')}

Ошибка: {str(e)}

Пожалуйста, проверьте логи для получения подробной информации.
                """
                
                self.send_notification(subject, body, is_error=True)
            
            logger.error(f"Автоматическое обновление завершилось с ошибкой: {e}")
            return error_report


def main():
    """Основная функция для запуска из командной строки"""
    import argparse

    _init_auto_update_logging()

    parser = argparse.ArgumentParser(description='Автоматическое обновление Encar')
    parser.add_argument('--config', help='Путь к файлу конфигурации')
    parser.add_argument('--type', choices=['daily', 'full'], default='daily', help='Тип обновления')
    parser.add_argument('--workers', type=int, default=5, help='Количество потоков')
    
    args = parser.parse_args()
    
    # Загрузка конфигурации
    config = {}
    if args.config and os.path.exists(args.config):
        import json
        with open(args.config, 'r') as f:
            config = json.load(f)
    
    # Обновление конфигурации аргументами командной строки
    if 'update_config' not in config:
        config['update_config'] = {}
    config['update_config']['update_type'] = args.type
    config['update_config']['max_workers'] = args.workers
    
    # Запуск обновления
    manager = AutoUpdateManager(config)
    result = manager.run_update()
    
    # Вывод результата
    print(f"Результат обновления: {result['status']}")
    if result['status'] == 'success':
        res = result.get("result") or {}
        if isinstance(res, dict):
            print(f"Обработано автомобилей: {res.get('total_processed', '— (см. лог encar_daily_update)')}")
        else:
            print(f"Результат: {res}")
    else:
        print(f"Ошибка: {result.get('error', result)}")
    
    # Возвращаем код завершения
    sys.exit(0 if result['status'] == 'success' else 1)


if __name__ == '__main__':
    main()

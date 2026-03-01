#!/usr/bin/env python3
"""
Быстрый старт системы Encar с PostgreSQL
"""

import sys
import os
import subprocess
import json
from datetime import datetime

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


def check_requirements():
    """Проверка наличия необходимых компонентов"""
    print("🔍 Проверка требований...")
    
    # Проверка Python
    try:
        import psycopg2
        print("✅ psycopg2 установлен")
    except ImportError:
        print("❌ psycopg2 не установлен. Установите: pip install psycopg2-binary")
        return False
    
    try:
        import requests
        print("✅ requests установлен")
    except ImportError:
        print("❌ requests не установлен. Установите: pip install requests")
        return False
    
    try:
        import pandas
        print("✅ pandas установлен")
    except ImportError:
        print("❌ pandas не установлен. Установите: pip install pandas")
        return False
    
    return True


def check_postgresql():
    """Проверка доступности PostgreSQL"""
    print("🗄️ Проверка PostgreSQL...")
    
    try:
        # Проверяем доступность psql
        result = subprocess.run(['psql', '--version'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print(f"✅ PostgreSQL доступен: {result.stdout.strip()}")
            return True
        else:
            print("❌ PostgreSQL не доступен")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("❌ PostgreSQL не найден в PATH")
        print("💡 Убедитесь, что PostgreSQL установлен и добавлен в PATH")
        return False


def create_database():
    """Создание базы данных"""
    print("🏗️ Создание базы данных...")
    
    try:
        # Запрашиваем параметры подключения
        host = input("Хост PostgreSQL (по умолчанию: localhost): ") or "localhost"
        port = input("Порт PostgreSQL (по умолчанию: 5432): ") or "5432"
        user = input("Пользователь PostgreSQL (по умолчанию: postgres): ") or "postgres"
        password = input("Пароль PostgreSQL: ")
        database = input("Имя базы данных (по умолчанию: encar): ") or "encar"
        
        # Проверяем подключение
        import psycopg2
        
        conn_params = {
            'host': host,
            'port': port,
            'user': user,
            'password': password
        }
        
        # Проверяем подключение к серверу
        conn = psycopg2.connect(**conn_params)
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Проверяем существование базы данных
        cursor.execute(f"SELECT 1 FROM pg_database WHERE datname='{database}'")
        exists = cursor.fetchone()
        
        if not exists:
            print(f"🗄️ Создание базы данных {database}...")
            cursor.execute(f"CREATE DATABASE {database}")
            print(f"✅ База данных {database} создана")
        else:
            print(f"✅ База данных {database} уже существует")
        
        # Проверяем подключение к базе данных
        conn.close()
        conn_params['database'] = database
        conn = psycopg2.connect(**conn_params)
        conn.close()
        
        print("✅ Подключение к базе данных успешно")
        
        # Сохраняем конфигурацию
        config = {
            "db_config": {
                "host": host,
                "port": int(port),
                "database": database,
                "user": user,
                "password": password
            },
            "update_config": {
                "max_workers": 5,
                "update_type": "daily"
            },
            "notification_config": {
                "enabled": False,
                "smtp": {
                    "server": "smtp.gmail.com",
                    "port": 587,
                    "username": "your-email@gmail.com",
                    "password": "your-app-password",
                    "to_email": "admin@yourcompany.com"
                },
                "send_on_success": True,
                "send_on_error": True
            },
            "backup_config": {
                "enabled": True,
                "backup_dir": "./backups",
                "keep_days": 7
            }
        }
        
        with open('config.json', 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print("✅ Конфигурационный файл сохранен: config.json")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка создания базы данных: {e}")
        return False


def test_system():
    """Тестирование системы"""
    print("🧪 Тестирование системы...")
    
    try:
        from postgresql_database import PostgreSQLDatabase
        from auto_update import AutoUpdateManager
        
        # Загружаем конфигурацию
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Тестируем базу данных
        db = PostgreSQLDatabase(**config['db_config'])
        print("✅ Подключение к PostgreSQL")
        
        # Тестируем менеджер
        manager = AutoUpdateManager(config)
        print("✅ Инициализация менеджера обновления")
        
        # Проверка состояния системы
        health = manager.get_system_health_check()
        if health['status'] == 'healthy':
            print("✅ Система работает нормально")
        else:
            print(f"⚠️  Проблемы с системой: {health['message']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования системы: {e}")
        return False


def run_initial_scan():
    """Запуск первоначального сканирования"""
    print("🔄 Запуск первоначального сканирования...")
    
    try:
        from auto_update import AutoUpdateManager
        
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Меняем тип обновления на полный скан
        config['update_config']['update_type'] = 'full'
        config['update_config']['max_workers'] = 3  # Начнем с меньшего количества потоков
        
        manager = AutoUpdateManager(config)
        result = manager.run_update()
        
        if result['status'] == 'success':
            print("✅ Первоначальное сканирование завершено")
            print(f"   Обработано автомобилей: {result['result'].get('total_processed', 0)}")
            print(f"   Успешно: {result['result'].get('successful', 0)}")
            print(f"   Ошибки: {result['result'].get('failed', 0)}")
            return True
        else:
            print(f"❌ Ошибка сканирования: {result.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка первоначального сканирования: {e}")
        return False


def setup_automation():
    """Настройка автоматического обновления"""
    print("⏰ Настройка автоматического обновления...")
    
    try:
        import platform
        
        system = platform.system()
        
        if system in ['Linux', 'Darwin']:  # Linux или macOS
            print("🔧 Настраиваем cron для Linux/macOS...")
            
            # Запрашиваем время обновления
            update_time = input("Время ежедневного обновления (в формате HH:MM, по умолчанию: 03:00): ") or "03:00"
            
            # Получаем путь к текущей директории
            current_dir = os.getcwd()
            
            # Создаем cron задание
            minute = update_time.split(':')[0]
            hour = update_time.split(':')[1]
            
            cron_command = f"{minute} {hour} * * * cd {current_dir} && python3 auto_update.py --config config.json --type daily --workers 5 >> auto_update_cron.log 2>&1"
            
            # Добавляем в cron
            try:
                # Получаем текущие cron задания
                result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
                current_cron = result.stdout if result.returncode == 0 else ""
                
                # Добавляем новое задание
                new_cron = current_cron + cron_command + "\n"
                
                # Сохраняем cron задания
                subprocess.run(['crontab', '-'], input=new_cron, text=True)
                
                print(f"✅ Cron задание добавлено: {update_time} ежедневно")
                print(f"   Команда: python3 auto_update.py --config config.json --type daily --workers 5")
                
            except Exception as e:
                print(f"⚠️  Не удалось автоматически настроить cron: {e}")
                print(f"💡 Вручную добавьте в cron: {cron_command}")
        
        elif system == 'Windows':
            print("🔧 Настраиваем Планировщик задач для Windows...")
            
            # Запрашиваем время обновления
            update_time = input("Время ежедневного обновления (в формате HH:MM, по умолчанию: 03:00): ") or "03:00"
            
            # Создаем XML для задачи
            current_dir = os.getcwd()
            
            xml_content = f'''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Date>{datetime.now().strftime('%Y-%m-%d')}T{datetime.now().strftime('%H:%M:%S')}</Date>
    <Author>Encar Auto Update</Author>
    <Description>Автоматическое обновление данных Encar</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>{datetime.now().strftime('%Y-%m-%d')}T{update_time}</StartBoundary>
      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>{os.environ.get('USERNAME', 'Unknown')}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>False</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>False</StopIfGoingOnBatteries>
    <AllowHardTerminate>True</AllowHardTerminate>
    <StartWhenAvailable>True</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>True</RunOnlyIfNetworkAvailable>
    <AllowStartOnDemand>True</AllowStartOnDemand>
    <Enabled>True</Enabled>
    <Hidden>False</Hidden>
    <RunOnlyIfIdle>False</RunOnlyIfIdle>
    <WakeToRun>False</WakeToRun>
    <ExecutionTimeLimit>PT12H</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>python</Command>
      <Arguments>auto_update.py --config config.json --type daily --workers 5</Arguments>
      <WorkingDirectory>{current_dir}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>'''
            
            # Сохраняем XML файл
            with open('encar_update_task.xml', 'w', encoding='utf-8') as f:
                f.write(xml_content)
            
            # Импортируем задачу
            try:
                subprocess.run(['schtasks', '/Create', '/XML', 'encar_update_task.xml', '/TN', 'Encar Auto Update', '/F'], 
                             check=True, capture_output=True)
                print(f"✅ Задание в Планировщике задач создано: {update_time} ежедневно")
                print(f"   Команда: python auto_update.py --config config.json --type daily --workers 5")
                
                # Удаляем временный XML файл
                os.remove('encar_update_task.xml')
                
            except subprocess.CalledProcessError as e:
                print(f"⚠️  Не удалось создать задание в Планировщике задач: {e}")
                print("💡 Создайте задание вручную через Планировщик задач")
        
        else:
            print(f"⚠️  Автоматическая настройка не поддерживается для {system}")
            print("💡 Настройте cron или Планировщик задач вручную")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка настройки автоматического обновления: {e}")
        return False


def show_help():
    """Показывает помощь по использованию"""
    print("\n" + "=" * 60)
    print("📚 Руководство по использованию")
    print("=" * 60)
    
    print("\n🚀 Основные команды:")
    print("   python auto_update.py --config config.json --type daily    # Ежедневное обновление")
    print("   python auto_update.py --config config.json --type full     # Полный прогон")
    print("   python test_postgresql.py                                  # Тестирование системы")
    
    print("\n📊 Мониторинг:")
    print("   tail -f auto_update.log           # Просмотр логов (Linux/macOS)")
    print("   type auto_update.log              # Просмотр логов (Windows)")
    print("   crontab -l                        # Просмотр cron заданий")
    print("   schtasks /Query /TN \"Encar Auto Update\"  # Просмотр задачи (Windows)")
    
    print("\n🔧 Управление:")
    print("   crontab -e                        # Редактирование cron")
    print("   schtasks /Delete /TN \"Encar Auto Update\" # Удаление задачи (Windows)")
    print("   python quick_start.py             # Быстрый старт")
    
    print("\n📁 Файлы:")
    print("   config.json           - Конфигурация системы")
    print("   auto_update.log       - Логи обновления")
    print("   auto_update_cron.log  - Логи cron заданий")
    print("   backups/              - Резервные копии базы данных")
    
    print("\n⚠️  Важно:")
    print("   - Регулярно проверяйте логи на наличие ошибок")
    print("   - Настройте резервное копирование базы данных")
    print("   - Мониторьте размер базы данных")
    print("   - Обновляйте конфигурацию при изменении параметров")
    
    print("\n💡 Поддержка:")
    print("   - Проверьте README_POSTGRESQL.md для подробной документации")
    print("   - Обратитесь за помощью при возникновении проблем")


def main():
    """Основная функция быстрого старта"""
print("🚀 Быстрый старт системы Encar с PostgreSQL")
    print("=" * 60)
    
    # Шаг 1: Проверка требований
    if not check_requirements():
        print("\n❌ Проверка требований не пройдена")
        sys.exit(1)
    
    # Шаг 2: Проверка PostgreSQL
    if not check_postgresql():
        print("\n❌ PostgreSQL не доступен")
        print("💡 Установите PostgreSQL и добавьте его в PATH")
        sys.exit(1)
    
    # Шаг 3: Создание базы данных
    if not create_database():
        print("\n❌ Не удалось создать базу данных")
        sys.exit(1)
    
    # Шаг 4: Тестирование системы
    if not test_system():
        print("\n❌ Тестирование системы не пройдено")
        print("💡 Проверьте конфигурацию и подключение к PostgreSQL")
        sys.exit(1)
    
    # Шаг 5: Предложение запустить первоначальное сканирование
    print("\n" + "=" * 60)
    print("📋 Доступные действия:")
    print("1. Запустить первоначальное сканирование (рекомендуется)")
    print("2. Настроить только автоматическое обновление")
    print("3. Пропустить и использовать систему вручную")
    
    choice = input("\nВыберите действие (1-3): ")
    
    if choice == '1':
        if run_initial_scan():
            print("✅ Первоначальное сканирование завершено")
        else:
            print("❌ Первоначальное сканирование не удалось")
    
    elif choice == '2':
        print("⏭️  Пропускаем первоначальное сканирование")
    
    elif choice == '3':
        print("⏭️  Пропускаем первоначальное сканирование")
    
    else:
        print("⚠️  Неверный выбор, пропускаем сканирование")
    
    # Шаг 6: Настройка автоматического обновления
    print("\n" + "=" * 60)
    setup_auto = input("Настроить автоматическое обновление? (y/n): ").lower().strip()
    
    if setup_auto in ['y', 'yes', 'да', 'д']:
        if setup_automation():
            print("✅ Автоматическое обновление настроено")
        else:
            print("❌ Не удалось настроить автоматическое обновление")
    else:
        print("⏭️  Пропускаем настройку автоматического обновления")
    
    # Шаг 7: Показ помощи
    show_help()
    
    print("\n" + "=" * 60)
    print("🎉 Быстрый старт завершен!")
    print("💡 Система готова к использованию")
    print("=" * 60)


if __name__ == '__main__':
    main()
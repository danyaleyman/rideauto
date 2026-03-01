# Encar Parser - PostgreSQL Edition

Система парсинга и анализа автомобилей с сайта Encar с использованием PostgreSQL и автоматическим обновлением.

## Особенности

### 🚀 **PostgreSQL база данных**
- Высокая производительность и надежность
- Поддержка JSONB для гибкого хранения данных
- Оптимизированные индексы для быстрого поиска
- Масштабируемость для больших объемов данных

### 🔄 **Автоматическое обновление**
- Ежедневное обновление в 3:00 утра
- Отслеживание изменений через хеши
- Резервное копирование базы данных
- Email уведомления о результатах

### 📊 **Улучшенная аналитика**
- Расширенная статистика производительности
- Мониторинг состояния системы
- Поиск по любым полям через JSONB
- Обнаружение дубликатов

## Требования

- Python 3.8+
- PostgreSQL 12+
- psycopg2-binary
- requests, pandas, openpyxl

## Установка

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Настройка PostgreSQL

#### Linux/macOS:
```bash
# Ubuntu/Debian
sudo apt-get install postgresql postgresql-contrib

# CentOS/RHEL
sudo yum install postgresql postgresql-server

# macOS
brew install postgresql
```

#### Windows:
Скачайте и установите PostgreSQL с [официального сайта](https://www.postgresql.org/download/windows/)

### 3. Создание базы данных

```sql
-- Подключитесь к PostgreSQL как суперпользователь
sudo -u postgres psql

-- Создайте базу данных
CREATE DATABASE encar;

-- Создайте пользователя (если нужно)
CREATE USER encar_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE encar TO encar_user;
```

### 4. Настройка системы

#### Автоматическая настройка:

**Для Linux/macOS:**
```bash
chmod +x setup_cron.sh
./setup_cron.sh
```

**Для Windows:**
```cmd
setup_task_scheduler.bat
```

#### Ручная настройка:

1. Отредактируйте `config.json` с вашими параметрами PostgreSQL
2. Запустите тест:
```bash
python auto_update.py --config config.json --type daily --workers 2
```

## Использование

### Ручное обновление

```bash
# Ежедневное обновление (только новые/измененные)
python auto_update.py --config config.json --type daily --workers 10

# Полный прогон всех автомобилей
python auto_update.py --config config.json --type full --workers 10
```

### Через конфигурационный файл

```bash
# Использование сохраненной конфигурации
python auto_update.py --config config.json
```

### Прямое использование системы

```python
from postgresql_database import PostgreSQLDatabase
from auto_update import AutoUpdateManager

# Создание базы данных
db = PostgreSQLDatabase(
    host="localhost",
    port=5432,
    database="encar",
    user="postgres",
    password="password"
)

# Создание менеджера обновления
manager = AutoUpdateManager({
    'db_config': {
        'host': 'localhost',
        'port': 5432,
        'database': 'encar',
        'user': 'postgres',
        'password': 'password'
    },
    'update_config': {
        'max_workers': 5,
        'update_type': 'daily'
    }
})

# Запуск обновления
result = manager.run_update()
```

## Автоматическое обновление

### Linux/macOS (cron)

Скрипт `setup_cron.sh` автоматически настроит cron задание:

```bash
# Просмотр cron заданий
crontab -l

# Редактирование cron заданий
crontab -e

# Пример задания (обновление в 3:00 утра)
0 3 * * * cd /path/to/project && python3 auto_update.py --config config.json --type daily --workers 5 >> auto_update_cron.log 2>&1
```

### Windows (Task Scheduler)

Скрипт `setup_task_scheduler.bat` создаст задание в Планировщике задач:

```cmd
# Просмотр заданий
schtasks /Query /TN "Encar Auto Update"

# Удаление задания
schtasks /Delete /TN "Encar Auto Update"

# Запуск задания вручную
schtasks /Run /TN "Encar Auto Update"
```

## Конфигурация

### Основные параметры

```json
{
    "db_config": {
        "host": "localhost",
        "port": 5432,
        "database": "encar",
        "user": "postgres",
        "password": "password"
    },
    "update_config": {
        "max_workers": 5,
        "update_type": "daily"
    },
    "notification_config": {
        "enabled": false,
        "smtp": {
            "server": "smtp.gmail.com",
            "port": 587,
            "username": "your-email@gmail.com",
            "password": "your-app-password",
            "to_email": "admin@yourcompany.com"
        },
        "send_on_success": true,
        "send_on_error": true
    },
    "backup_config": {
        "enabled": true,
        "backup_dir": "./backups",
        "keep_days": 7
    }
}
```

### Параметры базы данных

- `host`: Хост PostgreSQL сервера
- `port`: Порт PostgreSQL (по умолчанию 5432)
- `database`: Имя базы данных
- `user`: Имя пользователя
- `password`: Пароль пользователя

### Параметры обновления

- `max_workers`: Количество потоков для парсинга
- `update_type`: Тип обновления ('daily' или 'full')

### Параметры уведомлений

- `enabled`: Включить email уведомления
- `smtp.server`: SMTP сервер
- `smtp.port`: Порт SMTP
- `smtp.username`: Email для отправки
- `smtp.password`: Пароль или app password
- `smtp.to_email`: Email для получения уведомлений

### Параметры резервного копирования

- `enabled`: Включить резервное копирование
- `backup_dir`: Директория для резервных копий
- `keep_days`: Сколько дней хранить резервные копии

## API и функции

### PostgreSQLDatabase

```python
from postgresql_database import PostgreSQLDatabase

db = PostgreSQLDatabase(host="localhost", database="encar", user="postgres", password="password")

# Добавление/обновление автомобиля
car_data = {
    'inner_id': 'car123',
    'data': {'mark': 'BMW', 'model': 'X5', 'price': '50000'},
    'created_at': datetime.now().isoformat(),
    'updated_at': datetime.now().isoformat(),
    'last_seen': datetime.now().isoformat()
}
result = db.add_or_update_car(car_data)

# Получение автомобиля
car = db.get_car('car123')

# Поиск по фильтрам
bmw_cars = db.get_cars_by_filter({'mark': 'BMW', 'year': '2020'})

# Статистика
stats = db.get_stats()

# Статистика производительности
perf_stats = db.get_performance_stats()
```

### AutoUpdateManager

```python
from auto_update import AutoUpdateManager

manager = AutoUpdateManager(config)

# Ежедневное обновление
result = manager.run_daily_update()

# Полный скан
result = manager.run_full_scan()

# Проверка состояния системы
health = manager.get_system_health_check()

# Создание резервной копии
backup_file = manager.create_backup()
```

## Мониторинг и логирование

### Логи

- `auto_update.log` - Основные логи системы
- `auto_update_cron.log` - Логи cron заданий

### Статистика

```python
# Получение статистики
stats = db.get_stats()
print(f"Активных автомобилей: {stats['total_active']}")
print(f"Добавлено сегодня: {stats['added_today']}")
print(f"Обновлено сегодня: {stats['updated_today']}")

# Статистика производительности
perf = db.get_performance_stats()
print(f"Размер базы данных: {perf['size_info']['table_size']}")
```

### Health Check

```python
health = manager.get_system_health_check()
if health['status'] == 'healthy':
    print("✅ Система работает нормально")
else:
    print(f"❌ Проблемы с системой: {health['message']}")
```

## Производительность

### Оптимизации PostgreSQL

- **GIN индексы** для JSONB полей
- **WAL режим** для высокой производительности
- **Оптимизированный размер страницы** (4KB)
- **Кэширование** базы данных

### Рекомендации

1. **Настройка PostgreSQL**:
   ```sql
   -- Включить WAL режим
   ALTER SYSTEM SET wal_level = replica;
   
   -- Увеличить shared_buffers
   ALTER SYSTEM SET shared_buffers = '256MB';
   
   -- Настроить work_mem
   ALTER SYSTEM SET work_mem = '16MB';
   ```

2. **Мониторинг**:
   - Регулярно проверяйте размер базы данных
   - Контролируйте количество активных соединений
   - Мониторьте производительность запросов

3. **Резервное копирование**:
   - Автоматическое создание резервных копий
   - Хранение копий 7 дней
   - Возможность восстановления

## Устранение неполадок

### Распространенные проблемы

1. **Ошибка подключения к PostgreSQL**:
   ```bash
   # Проверьте, запущен ли PostgreSQL
   sudo systemctl status postgresql
   
   # Проверьте подключение
   psql -U postgres -h localhost
   ```

2. **Ошибки прав доступа**:
   ```sql
   -- Проверьте права пользователя
   GRANT ALL PRIVILEGES ON DATABASE encar TO username;
   GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO username;
   ```

3. **Проблемы с cron**:
   ```bash
   # Проверьте переменные окружения
   echo $PATH
   
   # Проверьте логи cron
   tail -f /var/log/cron.log
   ```

### Логи и диагностика

```bash
# Просмотр логов системы
tail -f auto_update.log

# Проверка состояния PostgreSQL
sudo systemctl status postgresql

# Проверка cron заданий
crontab -l
```

## Безопасность

### Рекомендации

1. **Пароли**: Используйте сложные пароли для PostgreSQL
2. **SSL**: Включите SSL соединение при необходимости
3. **Бэкапы**: Регулярно создавайте и проверяйте резервные копии
4. **Мониторинг**: Настройте мониторинг и уведомления

### Настройка SSL

```sql
-- Включить SSL в postgresql.conf
ssl = on
ssl_cert_file = 'server.crt'
ssl_key_file = 'server.key'
```

## Лицензия

Этот проект распространяется под лицензией MIT.

## Поддержка

Для вопросов и поддержки:
- Проверьте логи системы
- Убедитесь в правильности конфигурации
- Проверьте подключение к PostgreSQL
- Обратитесь за помощью в issues
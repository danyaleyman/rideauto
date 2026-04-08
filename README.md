# Prod Encar

Проект разделён на слои:

- **Фронт (Next.js)**: папка `web/` — каталог и карточка; бэкенд — FastAPI + Meilisearch + Postgres (см. `docs/ARCHITECTURE.md`, `docker-compose.yml`).
- **Backend**: папка `backend/` — FastAPI (`fastapi_app`), скраперы Encar/Dongchedi, синхронизация каталога в Postgres.

## Быстрый старт (backend)

```bash
pip install -r backend/requirements.txt
python backend/run_system.py --setup
python backend/run_system.py --daily
```

Конфиг: `backend/config.json`

## Открыть сайт (разработка)

```bash
cd web && npm install && npm run dev
```

Опциональный статический дамп каталога (CDN/отладка без Meilisearch): флаги у [`backend/postgres_catalog_sync.py`](backend/postgres_catalog_sync.py) (`--write-static-json` → `web/public/cars.json` и чанки в `web/public/data/`). Справочники для билда копируются из `data/` скриптом `web/scripts/sync-static-data.mjs`.

**Ночное обновление:** в [`backend/config.json`](backend/config.json) `update_config.catalog_encar_nightly` (по умолчанию `true`) — после цикла PostgreSQL вызывается `encar_daily_update.py --once` (discover, sold-check, скрейпер в Postgres). Без доступного Postgres `auto_update` завершается с ошибкой.

Глубина списка Encar задаётся в [`scraper_config.yaml`](scraper_config.yaml): `max_list_offset: 0` означает проход до пустого ответа (с верхней границей `list_offset_hard_cap`). Дополнительные срезы запроса — `list_q_suffixes`.

## API каталога (FastAPI)

```bash
cd backend && uvicorn fastapi_app.main:app --host 0.0.0.0 --port 8080
```

Эндпоинты (см. `docs/openapi.yaml`, `backend/fastapi_app/`): `GET /api/health`, `GET /api/cars`, `GET /api/search`, `GET /api/facets`, `GET /api/filters`, `GET /api/car/{id}`, `GET /api/similar`. Данные — PostgreSQL + Meilisearch; переменные окружения с префиксом `WRA_` (см. `fastapi_app.config.Settings`).

## Runbook: scrape -> reindex -> smoke

Короткий цикл после обновления Китая (из корня проекта):

```bash
# 1) Scrape (пример: China)
docker compose exec -T api python backend/dongchedi_scraper.py --config backend/dongchedi_scraper.yaml --max-pages 200

# 2) Reindex Meilisearch
docker compose exec -T api python infrastructure/meilisearch/sync_meilisearch.py --batch-size 500

# 3) Smoke checks
curl -fsS "http://127.0.0.1:8080/api/health"
curl -fsS "http://127.0.0.1:8080/api/cars?region=china&limit=12" | python -m json.tool
curl -fsS "http://127.0.0.1:3000/catalog?region=china" > /dev/null
```

## VPS production setup (Nginx + systemd)

В проект добавлен готовый набор:

- `deploy/nginx/prod-encar.conf`
- `deploy/systemd/prod-encar-api.service`
- `deploy/systemd/prod-encar-auto-update.service`
- `deploy/systemd/prod-encar-auto-update.timer`
- `deploy/systemd/dongchedi-update.service` + `dongchedi-update.timer` (или **`prod-dongchedi-update.*`** для пользователя `prod-encar`) — Китай в **`encar_china.db`**, полночь **Asia/Yekaterinburg**, как у корейского обновления
- `deploy/deploy_prod.sh`

Быстрый деплой на Linux VPS:

```bash
chmod +x deploy/deploy_prod.sh
./deploy/deploy_prod.sh
```

По умолчанию ставится в `/opt/prod-encar`, API (uvicorn FastAPI) слушает `127.0.0.1:8080`, Nginx публикует Next и проксирует `/api/*`. Китайский каталог — те же таблицы Postgres (`source`/region в данных), не отдельный `encar_china.db` в рантайме API.

## Security hardening (рекомендуется)

Ниже набор команд для Ubuntu 22.04, чтобы безопасно разместить проект на VPS.

### 1) Сетевой доступ (UFW)

Открывай только нужные порты:

```bash
sudo apt-get update
sudo apt-get install -y ufw

# SSH-порт нужно знать заранее (чтобы не залочить себя).
# Уточни порт SSH на VPS, затем используй его в команде ниже.
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow SSH_PORT/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

sudo ufw enable
sudo ufw status verbose
```

### 2) Fail2ban (защита от брутфорса SSH)

```bash
sudo apt-get install -y fail2ban
sudo cp /etc/fail2ban/jail.conf /etc/fail2ban/jail.local

# базовые джайлы
sudo tee -a /etc/fail2ban/jail.local > /dev/null <<'EOF'
[sshd]
enabled = true
port = 22
logpath = /var/log/auth.log
maxretry = 5
findtime = 10m
bantime = 1h

[nginx-http-auth]
enabled = true
EOF

sudo systemctl restart fail2ban
sudo systemctl status fail2ban --no-pager
```

### 3) Разрешение на сервисы без root

В systemd unit’ах используется отдельный пользователь `prod-encar`, deploy-скрипт создаёт его и выдаёт права на `/opt/prod-encar`.

Проверь, что systemd unit’ы активны:

```bash
systemctl status prod-encar-api.service --no-pager
systemctl status prod-encar-auto-update.timer --no-pager
```

В `backend/config.json` при необходимости отключите `update_config.catalog_encar_nightly`, если ночной `encar_daily_update` не нужен. Длинный пост-экспорт `auto_learn_engine_map` можно отключить переменной `SKIP_LEARN_ENGINE_MAP=1` в `/etc/default/prod-encar` (см. `deploy/systemd/prod-encar-auto-update.service`).

### 4) TLS (HTTPS) через certbot

Если есть домен, включи TLS:

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d YOUR_DOMAIN -d www.YOUR_DOMAIN
sudo certbot renew --dry-run
```

## Документация

- `backend/README_POSTGRESQL.md`
- `backend/RUN_SYSTEM_README.md`
- `backend/SCRAPER_README.md`

### Ручная настройка

1. **Установите PostgreSQL**:
   - Linux: `sudo apt-get install postgresql`
   - macOS: `brew install postgresql`
   - Windows: [Скачать с официального сайта](https://www.postgresql.org/download/windows/)

2. **Создайте базу данных**:
   ```sql
   CREATE DATABASE encar;
   CREATE USER encar_user WITH PASSWORD 'your_password';
   GRANT ALL PRIVILEGES ON DATABASE encar TO encar_user;
   ```

3. **Настройте конфигурацию** в `config.json`

## 🔧 Использование

### Универсальный запуск (рекомендуется)

```bash
# Стандартный запуск (умное обновление)
python run_system.py

# Умное обновление (автоопределение режима)
python run_system.py --smart

# Только настройка системы
python run_system.py --setup

# Только тестирование системы
python run_system.py --test

# Ежедневное обновление
python run_system.py --daily

# Полный прогон
python run_system.py --full

# Настройка автоматического обновления
python run_system.py --auto

# Быстрый запуск (только обновление)
python run_system.py --quick
```

**💡 Логика умного обновления:**
- **Пустая база данных** → Запуск `parser_full.py` (первоначальная загрузка)
- **База есть, но сканирования не было** → Полное обновление
- **Данные устарели >7 дней** → Полное обновление
- **Данные устарели >1 дня** → Ежедневное обновление
- **Данные актуальны** → Ежедневное обновление

### Прямой запуск (для продвинутых пользователей)

```bash
# Ежедневное обновление (только новые/измененные)
python auto_update.py --config config.json --type daily --workers 10

# Полный прогон всех автомобилей
python auto_update.py --config config.json --type full --workers 10

# Тестирование системы
python test_postgresql.py

# Быстрый старт и настройка
python quick_start.py
```

### Автоматическое обновление

#### Linux/macOS (cron)
```bash
# Автоматическая настройка
chmod +x setup_cron.sh
./setup_cron.sh

# Или вручную
crontab -e
# Добавьте: 0 3 * * * cd /path/to/project && python3 auto_update.py --config config.json --type daily --workers 5 >> auto_update_cron.log 2>&1
```

#### Windows (Task Scheduler)
```cmd
# Автоматическая настройка
setup_task_scheduler.bat

# Или вручную через Планировщик задач
```

## 📊 Возможности

### 🗄️ **PostgreSQL база данных**

- **JSONB хранение** - гибкое хранение любых данных об автомобилях
- **Оптимизированные индексы** - быстрый поиск по любым полям
- **WAL режим** - высокая производительность записи
- **Масштабируемость** - поддержка больших объемов данных

### 🔄 **Автоматическое обновление**

- **Ежедневное обновление** в заданное время
- **Отслеживание изменений** через хеши данных
- **Резервное копирование** перед каждым обновлением
- **Email уведомления** о результатах

### 📈 **Аналитика и мониторинг**

- **Расширенная статистика** производительности
- **Health check** системы
- **Поиск дубликатов** по VIN
- **Мониторинг роста базы данных**

### 🔍 **Гибкий поиск**

```python
# Поиск по любым полям
bmw_cars = db.get_cars_by_filter({'mark': 'BMW', 'year': '2020'})

# Поиск с лимитом
recent_cars = db.get_cars_by_filter({'year': '2023'}, limit=100)

# Получение всех активных автомобилей
all_cars = db.get_all_active_cars(limit=1000)
```

## 📁 Структура проекта

```
├── postgresql_database.py    # PostgreSQL база данных
├── auto_update.py           # Автоматическое обновление
├── quick_start.py           # Быстрый старт
├── test_postgresql.py       # Тестирование системы
├── setup_cron.sh           # Настройка cron (Linux/macOS)
├── setup_task_scheduler.bat # Настройка Task Scheduler (Windows)
├── config.json             # Конфигурация системы
├── requirements.txt        # Зависимости
├── README_POSTGRESQL.md    # Подробная документация
└── README.md              # Этот файл
```

## ⚙️ Конфигурация

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
        }
    },
    "backup_config": {
        "enabled": true,
        "backup_dir": "./backups",
        "keep_days": 7
    }
}
```

## 📈 Производительность

### Тесты производительности

- **Вставка**: до 1000 авто/сек
- **Поиск**: до 100 запросов/сек
- **Выборка**: до 5000 авто/сек
- **Хранение**: до 1M+ автомобилей

### Оптимизации

- **GIN индексы** для JSONB полей
- **WAL режим** для высокой производительности
- **Оптимизированный размер страницы** (4KB)
- **Эффективное кэширование**

## 🔍 API

### PostgreSQLDatabase

```python
from postgresql_database import PostgreSQLDatabase

db = PostgreSQLDatabase(host="localhost", database="encar", user="postgres", password="password")

# Добавление/обновление
result = db.add_or_update_car(car_data)

# Получение автомобиля
car = db.get_car('inner_id')

# Поиск по фильтрам
cars = db.get_cars_by_filter({'mark': 'BMW'})

# Статистика
stats = db.get_stats()

# Производительность
perf = db.get_performance_stats()
```

### AutoUpdateManager

```python
from auto_update import AutoUpdateManager

manager = AutoUpdateManager(config)

# Ежедневное обновление
result = manager.run_daily_update()

# Полный скан
result = manager.run_full_scan()

# Health check
health = manager.get_system_health_check()

# Резервное копирование
backup = manager.create_backup()
```

## 🚨 Устранение неполадок

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

### Логи

- `auto_update.log` - Основные логи системы
- `auto_update_cron.log` - Логи cron заданий
- `quick_start.log` - Логи настройки

## 🔄 Эксплуатация каталога

Каталог работает только через PostgreSQL + Meilisearch.

Базовая проверка после деплоя:

```bash
python -m pytest backend/tests -q
cd web && npm run build
```

## 📚 Документация

- [README_POSTGRESQL.md](./README_POSTGRESQL.md) - Подробная документация
- [config.json](./config.json) - Пример конфигурации
- [test_postgresql.py](./test_postgresql.py) - Примеры использования

## 🤝 Поддержка

Для вопросов и поддержки:

1. Проверьте логи системы
2. Убедитесь в правильности конфигурации
3. Проверьте подключение к PostgreSQL
4. Обратитесь за помощью в issues

## 📄 Лицензия

Этот проект распространяется под лицензией MIT.

## 🙏 Благодарности

Спасибо за использование системы Encar Parser! Надеемся, что PostgreSQL версия принесет вам больше удобства и производительности.

---

**💡 Совет**: Для начала работы запустите `python quick_start.py` - это автоматически настроит всю систему!



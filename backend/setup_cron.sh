#!/bin/bash
# Скрипт настройки автоматического обновления для Linux/macOS

echo "=== Настройка автоматического обновления Encar ==="

# Проверка наличия Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 не найден. Пожалуйста, установите Python3."
    exit 1
fi

# Проверка наличия pip
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 не найден. Пожалуйста, установите pip3."
    exit 1
fi

# Установка зависимостей
echo "📦 Установка зависимостей..."
pip3 install -r requirements.txt

# Проверка наличия PostgreSQL
if ! command -v psql &> /dev/null; then
    echo "❌ PostgreSQL не найден. Пожалуйста, установите PostgreSQL."
    echo "Для Ubuntu/Debian: sudo apt-get install postgresql postgresql-contrib"
    echo "Для CentOS/RHEL: sudo yum install postgresql postgresql-server"
    echo "Для macOS: brew install postgresql"
    exit 1
fi

# Создание базы данных (если не существует)
echo "🗄️ Проверка базы данных..."
read -p "Введите имя пользователя PostgreSQL (по умолчанию: postgres): " pg_user
pg_user=${pg_user:-postgres}

read -p "Введите имя базы данных (по умолчанию: encar): " db_name
db_name=${db_name:-encar}

read -s -p "Введите пароль PostgreSQL: " pg_password
echo

# Проверка подключения к PostgreSQL
export PGPASSWORD="$pg_password"
if psql -U "$pg_user" -h localhost -c "SELECT 1;" &> /dev/null; then
    echo "✅ Подключение к PostgreSQL успешно"
else
    echo "❌ Не удалось подключиться к PostgreSQL. Проверьте логин и пароль."
    exit 1
fi

# Создание базы данных
if ! psql -U "$pg_user" -h localhost -c "SELECT 1 FROM pg_database WHERE datname='$db_name';" | grep -q 1; then
    echo "🗄️ Создание базы данных $db_name..."
    createdb -U "$pg_user" -h localhost "$db_name"
    echo "✅ База данных создана"
else
    echo "✅ База данных $db_name уже существует"
fi

# Тестирование подключения к базе данных
if psql -U "$pg_user" -h localhost -d "$db_name" -c "SELECT 1;" &> /dev/null; then
    echo "✅ Подключение к базе данных успешно"
else
    echo "❌ Не удалось подключиться к базе данных"
    exit 1
fi

# Создание конфигурационного файла
echo "⚙️ Создание конфигурационного файла..."
cat > config.json << EOF
{
    "db_config": {
        "host": "localhost",
        "port": 5432,
        "database": "$db_name",
        "user": "$pg_user",
        "password": "$pg_password"
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
EOF

echo "✅ Конфигурационный файл создан: config.json"

# Тестирование системы
echo "🧪 Тестирование системы..."
if python3 auto_update.py --config config.json --type daily --workers 2; then
    echo "✅ Тестирование прошло успешно"
else
    echo "❌ Тестирование не удалось. Проверьте конфигурацию."
    exit 1
fi

# Настройка cron
echo "⏰ Настройка cron..."
read -p "Введите время для ежедневного обновления (в формате HH:MM, например 03:00): " update_time

if [ -z "$update_time" ]; then
    update_time="03:00"
fi

# Разбиваем время на часы и минуты
hour=$(echo $update_time | cut -d: -f1)
minute=$(echo $update_time | cut -d: -f2)

# Получаем путь к текущей директории
current_dir=$(pwd)

# Создаем cron задание
(crontab -l 2>/dev/null; echo "$minute $hour * * * cd $current_dir && python3 auto_update.py --config config.json --type daily --workers 5 >> auto_update_cron.log 2>&1") | crontab -

echo "✅ Cron задание добавлено:"
echo "   Время: $update_time ежедневно"
echo "   Команда: python3 auto_update.py --config config.json --type daily --workers 5"
echo "   Логи: auto_update_cron.log"

# Проверка cron задания
echo "📋 Проверка cron заданий:"
crontab -l | grep auto_update

echo ""
echo "🎉 Настройка автоматического обновления завершена!"
echo ""
echo "Доступные команды:"
echo "  python3 auto_update.py --config config.json --type daily    # Ежедневное обновление"
echo "  python3 auto_update.py --config config.json --type full     # Полный прогон"
echo "  crontab -l                                                  # Просмотр cron заданий"
echo "  crontab -e                                                  # Редактирование cron заданий"
echo ""
echo "Логи:"
echo "  auto_update.log     - Логи автоматического обновления"
echo "  auto_update_cron.log - Логи cron заданий"
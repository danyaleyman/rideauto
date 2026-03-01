@echo off
REM Скрипт настройки автоматического обновления для Windows

echo === Настройка автоматического обновления Encar ===

REM Проверка наличия Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python не найден. Пожалуйста, установите Python.
    pause
    exit /b 1
)

REM Проверка наличия pip
pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ pip не найден. Пожалуйста, установите pip.
    pause
    exit /b 1
)

REM Установка зависимостей
echo 📦 Установка зависимостей...
pip install -r requirements.txt

REM Проверка наличия PostgreSQL
where psql >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ PostgreSQL не найден. Пожалуйста, установите PostgreSQL.
    echo Для Windows: https://www.postgresql.org/download/windows/
    pause
    exit /b 1
)

REM Создание базы данных (если не существует)
echo 🗄️ Проверка базы данных...

set /p "pg_user=Введите имя пользователя PostgreSQL (по умолчанию: postgres): "
if "%pg_user%"=="" set pg_user=postgres

set /p "db_name=Введите имя базы данных (по умолчанию: encar): "
if "%db_name%"=="" set db_name=encar

set /p "pg_password=Введите пароль PostgreSQL: "

REM Проверка подключения к PostgreSQL
set PGPASSWORD=%pg_password%
psql -U %pg_user% -h localhost -c "SELECT 1;" >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Не удалось подключиться к PostgreSQL. Проверьте логин и пароль.
    pause
    exit /b 1
)
echo ✅ Подключение к PostgreSQL успешно

REM Создание базы данных
psql -U %pg_user% -h localhost -c "SELECT 1 FROM pg_database WHERE datname='%db_name%';" | find "1" >nul
if %errorlevel% neq 0 (
    echo 🗄️ Создание базы данных %db_name%...
    createdb -U %pg_user% -h localhost %db_name%
    if %errorlevel% neq 0 (
        echo ❌ Не удалось создать базу данных
        pause
        exit /b 1
    )
    echo ✅ База данных создана
) else (
    echo ✅ База данных %db_name% уже существует
)

REM Тестирование подключения к базе данных
psql -U %pg_user% -h localhost -d %db_name% -c "SELECT 1;" >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Не удалось подключиться к базе данных
    pause
    exit /b 1
)
echo ✅ Подключение к базе данных успешно

REM Создание конфигурационного файла
echo ⚙️ Создание конфигурационного файла...
(
echo {
echo     "db_config": {
echo         "host": "localhost",
echo         "port": 5432,
echo         "database": "%db_name%",
echo         "user": "%pg_user%",
echo         "password": "%pg_password%"
echo     },
echo     "update_config": {
echo         "max_workers": 5,
echo         "update_type": "daily"
echo     },
echo     "notification_config": {
echo         "enabled": false,
echo         "smtp": {
echo             "server": "smtp.gmail.com",
echo             "port": 587,
echo             "username": "your-email@gmail.com",
echo             "password": "your-app-password",
echo             "to_email": "admin@yourcompany.com"
echo         },
echo         "send_on_success": true,
echo         "send_on_error": true
echo     },
echo     "backup_config": {
echo         "enabled": true,
echo         "backup_dir": "./backups",
echo         "keep_days": 7
echo     }
echo }
) > config.json

echo ✅ Конфигурационный файл создан: config.json

REM Тестирование системы
echo 🧪 Тестирование системы...
python auto_update.py --config config.json --type daily --workers 2
if %errorlevel% neq 0 (
    echo ❌ Тестирование не удалось. Проверьте конфигурацию.
    pause
    exit /b 1
)
echo ✅ Тестирование прошло успешно

REM Настройка задания в Планировщике задач
echo ⏰ Настройка Планировщика задач...

set /p "update_time=Введите время для ежедневного обновления (в формате HH:MM, например 03:00): "
if "%update_time%"=="" set update_time=03:00

REM Получаем путь к текущей директории
set "current_dir=%cd%"

REM Создаем XML файл для импорта в Планировщик задач
(
echo ^<?xml version="1.0" encoding="UTF-16"?^>
echo ^<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"^>
echo   ^<RegistrationInfo^>
echo     ^<Date^>%date%T%time%^</Date^>
echo     ^<Author^>Encar Auto Update^</Author^>
echo     ^<Description^>Автоматическое обновление данных Encar^</Description^>
echo   ^</RegistrationInfo^>
echo   ^<Triggers^>
echo     ^<CalendarTrigger^>
echo       ^<StartBoundary^>%date%T%update_time%^</StartBoundary^>
echo       ^<ScheduleByDay^>
echo         ^<DaysInterval^>1^</DaysInterval^>
echo       ^</ScheduleByDay^>
echo     ^</CalendarTrigger^>
echo   ^</Triggers^>
echo   ^<Principals^>
echo     ^<Principal id="Author"^>
echo       ^<UserId^>%USERNAME%^</UserId^>
echo       ^<LogonType^>InteractiveToken^</LogonType^>
echo       ^<RunLevel^>HighestAvailable^</RunLevel^>
echo     ^</Principal^>
echo   ^</Principals^>
echo   ^<Settings^>
echo     ^<MultipleInstancesPolicy^>IgnoreNew^</MultipleInstancesPolicy^>
echo     ^<DisallowStartIfOnBatteries^>False^</DisallowStartIfOnBatteries^>
echo     ^<StopIfGoingOnBatteries^>False^</StopIfGoingOnBatteries^>
echo     ^<AllowHardTerminate^>True^</AllowHardTerminate^>
echo     ^<StartWhenAvailable^>True^</StartWhenAvailable^>
echo     ^<RunOnlyIfNetworkAvailable^>True^</RunOnlyIfNetworkAvailable^>
echo     ^<IdleSettings^>
echo       ^<StopOnIdleEnd^>False^</StopOnIdleEnd^>
echo       ^<RestartOnIdle^>False^</RestartOnIdle^>
echo     ^</IdleSettings^>
echo     ^<AllowStartOnDemand^>True^</AllowStartOnDemand^>
echo     ^<Enabled^>True^</Enabled^>
echo     ^<Hidden^>False^</Hidden^>
echo     ^<RunOnlyIfIdle^>False^</RunOnlyIfIdle^>
echo     ^<WakeToRun^>False^</WakeToRun^>
echo     ^<ExecutionTimeLimit^>PT12H^</ExecutionTimeLimit^>
echo     ^<Priority^>7^</Priority^>
echo   ^</Settings^>
echo   ^<Actions Context="Author"^>
echo     ^<Exec^>
echo       ^<Command^>python^</Command^>
echo       ^<Arguments^>auto_update.py --config config.json --type daily --workers 5^</Arguments^>
echo       ^<WorkingDirectory^>%current_dir%^</WorkingDirectory^>
echo     ^</Exec^>
echo   ^</Actions^>
echo ^</Task^>
) > encar_update_task.xml

REM Импортируем задачу в Планировщик задач
schtasks /Create /XML encar_update_task.xml /TN "Encar Auto Update" /F

if %errorlevel% equ 0 (
    echo ✅ Задание в Планировщике задач создано
    echo    Время: %update_time% ежедневно
    echo    Команда: python auto_update.py --config config.json --type daily --workers 5
) else (
    echo ❌ Не удалось создать задание в Планировщике задач
)

REM Проверка созданного задания
echo 📋 Проверка задания в Планировщике задач:
schtasks /Query /TN "Encar Auto Update" /V /FO LIST

echo.
echo 🎉 Настройка автоматического обновления завершена!
echo.
echo Доступные команды:
echo   python auto_update.py --config config.json --type daily    # Ежедневное обновление
echo   python auto_update.py --config config.json --type full     # Полный прогон
echo   schtasks /Query /TN "Encar Auto Update"                    # Просмотр задания
echo   schtasks /Delete /TN "Encar Auto Update"                   # Удаление задания
echo.
echo Логи:
echo   auto_update.log     - Логи автоматического обновления
echo.
pause
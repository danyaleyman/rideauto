#!/bin/bash
# ===============================================
# Локальное ежедневное обновление баз Che168 + Encar
# ===============================================

LOG_DIR="/home/danyaleyman/rideauto/logs"
mkdir -p $LOG_DIR

LOG_FILE="$LOG_DIR/local_daily_update_$(date +%Y%m%d_%H%M%S).log"

# Функция для логирования в файл и на экран
log() {
    echo "$1" | tee -a $LOG_FILE
}

# Настройка окружения
cd ~/rideauto
source .venv/bin/activate
export DATABASE_URL="postgresql://wra:wra@localhost:5432/wra"

log "========================================="
log "🚀 Локальное обновление: $(date)"
log "========================================="
log ""

# Проверка Docker
if ! docker ps &>/dev/null; then
    log "❌ Docker не запущен! Запустите Docker Desktop."
    exit 1
fi

# Проверка PostgreSQL контейнера
if ! docker exec -it rideauto-postgres-1 psql -U wra -d wra -c "SELECT 1;" &>/dev/null; then
    log "❌ PostgreSQL контейнер не отвечает! Запустите: docker-compose up -d"
    exit 1
fi

# ==================== Che168 (Китай) ====================
log "📦 Обновление Che168 (Китай)..."
log "-----------------------------------------"

if [ -f "che168_scraper.yaml" ]; then
    python backend/che168_daily_update.py --once --config che168_scraper.yaml 2>&1 | tee -a $LOG_FILE
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        log "✅ Che168 обновлён успешно"
    else
        log "❌ Ошибка при обновлении Che168"
    fi
else
    log "❌ Файл che168_scraper.yaml не найден!"
fi

log ""

# ==================== Encar (Корея) ====================
log "📦 Обновление Encar (Корея)..."
log "-----------------------------------------"

if [ -f "scraper_config.yaml" ]; then
    python backend/encar_daily_update.py --once --config scraper_config.yaml 2>&1 | tee -a $LOG_FILE
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        log "✅ Encar обновлён успешно"
    else
        log "❌ Ошибка при обновлении Encar"
    fi
else
    log "❌ Файл scraper_config.yaml не найден!"
fi

log ""

# ==================== Статистика ====================
log "📊 Статистика после обновления:"
log "-----------------------------------------"

docker exec -it rideauto-postgres-1 psql -U wra -d wra -c "
SELECT source, COUNT(*) FROM cars GROUP BY source;
" 2>&1 | tee -a $LOG_FILE

log ""
log "✅ Локальное обновление завершено: $(date)"
log "========================================="
log "📝 Лог сохранён: $LOG_FILE"

exit 0

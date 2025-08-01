#!/bin/bash
set -e

echo "🚀 Запуск Telegram Channel Finder Bot (Nixpacks)..."
echo "📁 Рабочая директория: $(pwd)"
echo "🐍 Версия Python: $(python --version)"

# Функция для логирования
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Функция для корректного завершения
cleanup() {
    log "🛑 Получен сигнал завершения..."
    if [ ! -z "$BOT_PID" ]; then
        log "⏹️ Остановка Telegram бота (PID: $BOT_PID)..."
        kill $BOT_PID 2>/dev/null || true
    fi
    if [ ! -z "$ADMIN_PID" ]; then
        log "⏹️ Остановка админ-панели (PID: $ADMIN_PID)..."
        kill $ADMIN_PID 2>/dev/null || true
    fi
    log "✅ Все процессы остановлены"
    exit 0
}

# Обработка сигналов
trap cleanup SIGTERM SIGINT

# Проверка переменных окружения
log "🔧 Проверка переменных окружения..."
if [ -z "$BOT_TOKEN" ]; then
    log "❌ ОШИБКА: BOT_TOKEN не установлен!"
    exit 1
fi

if [ -z "$API_ID" ] || [ -z "$API_HASH" ]; then
    log "❌ ОШИБКА: API_ID или API_HASH не установлены!"
    exit 1
fi

log "✅ Основные переменные окружения проверены"

# Создание необходимых директорий
log "📁 Создание необходимых директорий..."
mkdir -p logs backups uploads
log "✅ Директории созданы"

# Установка зависимостей
log "📦 Проверка зависимостей..."
if [ "$ENVIRONMENT" = "production" ] && [ -f "requirements-production.txt" ]; then
    pip install --no-cache-dir -r requirements-production.txt
    log "✅ Production зависимости установлены"
elif [ -f "requirements.txt" ]; then
    pip install --no-cache-dir -r requirements.txt
    log "✅ Зависимости установлены"
else
    log "⚠️ Файлы зависимостей не найдены"
fi

# Выполнение миграций базы данных
log "🗄️ Выполнение миграций базы данных..."
python -c "
import asyncio
import sys
import logging
from database.models import Database
from database.admin_migrations import run_admin_migrations

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_migrations():
    try:
        # Инициализация основной базы данных
        logger.info('Инициализация основной базы данных...')
        db = Database()
        await db.init_db()
        logger.info('✅ Основная база данных инициализирована')
        
        # Выполнение миграций админ-панели
        logger.info('Выполнение миграций админ-панели...')
        await run_admin_migrations()
        logger.info('✅ Миграции админ-панели выполнены')
        
        return True
    except Exception as e:
        logger.error(f'❌ Ошибка выполнения миграций: {e}')
        return False

# Запуск миграций
success = asyncio.run(run_migrations())
if not success:
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    log "❌ ОШИБКА: Миграции базы данных не выполнены!"
    exit 1
fi

log "✅ Миграции базы данных выполнены успешно"

# Проверка режима запуска
if [ "$NIXPACKS_PLAN_PROVIDERS" = "python" ] || [ "$ENVIRONMENT" = "production" ]; then
    log "🌐 Режим: Production (только Telegram бот)"
    
    # Запуск только Telegram бота в production
    log "📱 Запуск Telegram бота..."
    exec python main.py
else
    log "🔧 Режим: Development (бот + админ-панель)"
    
    # Запуск бота в фоне
    log "📱 Запуск Telegram бота..."
    python main.py &
    BOT_PID=$!
    log "✅ Telegram бот запущен (PID: $BOT_PID)"
    
    # Небольшая задержка
    sleep 3
    
    # Запуск админ-панели
    log "🌐 Запуск админ-панели..."
    python run_admin.py &
    ADMIN_PID=$!
    log "✅ Админ-панель запущена (PID: $ADMIN_PID)"
    
    log "🎉 Все сервисы запущены успешно!"
    log "📱 Telegram бот: PID $BOT_PID"
    log "🌐 Админ-панель: http://localhost:8080 (PID $ADMIN_PID)"
    
    # Ожидание завершения процессов
    wait
fi

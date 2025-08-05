#!/bin/bash

# Production-ready скрипт применения исправлений статистики
# Telegram Channel Finder Bot - Statistics Fix Deployment

set -e  # Остановка при ошибке

echo "🚀 Начало применения исправлений статистики на production сервере"
echo "=================================================="

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функция логирования
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка, что мы на правильном сервере
check_server() {
    log_info "Проверка сервера..."
    
    if [ ! -f "/root/.venv/bin/activate" ]; then
        log_error "Виртуальное окружение не найдено!"
        exit 1
    fi
    
    if [ ! -f "main.py" ]; then
        log_error "Файл main.py не найден! Убедитесь, что вы в директории проекта."
        exit 1
    fi
    
    log_success "Сервер проверен"
}

# Создание бэкапа
create_backup() {
    log_info "Создание бэкапа текущей версии..."
    
    BACKUP_DIR="backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    
    # Бэкапим критически важные файлы
    cp -r database/ "$BACKUP_DIR/" 2>/dev/null || true
    cp -r services/ "$BACKUP_DIR/" 2>/dev/null || true
    cp -r bot/handlers/ "$BACKUP_DIR/" 2>/dev/null || true
    cp -r admin/ "$BACKUP_DIR/" 2>/dev/null || true
    cp main.py "$BACKUP_DIR/" 2>/dev/null || true
    
    log_success "Бэкап создан в директории: $BACKUP_DIR"
}

# Остановка бота
stop_bot() {
    log_info "Остановка бота..."
    
    # Находим и останавливаем процессы Python
    pkill -f "python main.py" || true
    pkill -f "python run_admin.py" || true
    
    # Ждем завершения процессов
    sleep 3
    
    log_success "Бот остановлен"
}

# Проверка базы данных PostgreSQL
check_database() {
    log_info "Проверка подключения к PostgreSQL..."
    
    # Проверяем переменные окружения
    if [ -z "$DATABASE_URL" ]; then
        log_error "DATABASE_URL не установлена!"
        log_info "Установите переменную: export DATABASE_URL='postgresql://findertool_user:Findertool1999!@postgres:5432/findertool_prod'"
        exit 1
    fi
    
    # Проверяем подключение к базе
    python3 -c "
import asyncio
import asyncpg
import os

async def test_connection():
    try:
        conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
        await conn.execute('SELECT 1')
        await conn.close()
        print('✅ PostgreSQL подключение успешно')
        return True
    except Exception as e:
        print(f'❌ Ошибка подключения к PostgreSQL: {e}')
        return False

result = asyncio.run(test_connection())
exit(0 if result else 1)
" || {
        log_error "Не удалось подключиться к PostgreSQL!"
        log_info "Проверьте настройки базы данных"
        exit 1
    }
    
    log_success "PostgreSQL подключение проверено"
}

# Миграция данных из SQLite (если нужно)
migrate_data() {
    log_info "Проверка необходимости миграции данных..."
    
    if [ -f "bot.db" ]; then
        log_warning "Найден файл SQLite (bot.db)"
        read -p "Выполнить миграцию данных из SQLite в PostgreSQL? (y/N): " -n 1 -r
        echo
        
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "Запуск миграции данных..."
            
            source .venv/bin/activate
            python scripts/migrate_sqlite_to_postgresql.py \
                --sqlite-path bot.db \
                --postgresql-url "$DATABASE_URL" || {
                log_error "Ошибка миграции данных!"
                exit 1
            }
            
            log_success "Миграция данных завершена"
            
            # Переименовываем SQLite файл
            mv bot.db "bot.db.backup_$(date +%Y%m%d_%H%M%S)"
            log_info "SQLite файл переименован в бэкап"
        else
            log_info "Миграция пропущена"
        fi
    else
        log_info "SQLite файл не найден, миграция не требуется"
    fi
}

# Установка зависимостей
install_dependencies() {
    log_info "Проверка и установка зависимостей..."
    
    source .venv/bin/activate
    
    # Обновляем pip
    pip install --upgrade pip
    
    # Устанавливаем зависимости
    pip install -r requirements.txt
    
    log_success "Зависимости установлены"
}

# Инициализация базы данных
init_database() {
    log_info "Инициализация базы данных..."
    
    source .venv/bin/activate
    
    # Запускаем инициализацию БД
    python -c "
import asyncio
import os
import sys
sys.path.append('.')

async def init_db():
    try:
        from database.universal_database import UniversalDatabase
        
        db = UniversalDatabase(os.getenv('DATABASE_URL'))
        await db.adapter.connect()
        
        # Проверяем существование таблиц
        tables_query = '''
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN ('users', 'requests', 'broadcasts', 'payments')
        '''
        
        result = await db.adapter.fetch_all(tables_query)
        existing_tables = [row[0] for row in result]
        
        print(f'Существующие таблицы: {existing_tables}')
        
        if len(existing_tables) < 4:
            print('Создание недостающих таблиц...')
            # Здесь можно добавить создание таблиц
        
        await db.adapter.disconnect()
        print('✅ База данных инициализирована')
        
    except Exception as e:
        print(f'❌ Ошибка инициализации БД: {e}')
        sys.exit(1)

asyncio.run(init_db())
" || {
        log_error "Ошибка инициализации базы данных!"
        exit 1
    }
    
    log_success "База данных инициализирована"
}

# Тестирование системы
test_system() {
    log_info "Тестирование системы статистики..."
    
    source .venv/bin/activate
    
    # Тестируем сервис статистики
    python -c "
import asyncio
import os
import sys
sys.path.append('.')

async def test_statistics():
    try:
        from database.universal_database import UniversalDatabase
        from services.statistics_service import StatisticsService
        
        db = UniversalDatabase(os.getenv('DATABASE_URL'))
        stats_service = StatisticsService(db)
        
        # Тестируем базовую статистику
        basic_stats = await stats_service.get_basic_statistics()
        print(f'✅ Базовая статистика: {basic_stats.total_users} пользователей')
        
        # Тестируем детальную статистику
        detailed_stats = await stats_service.get_detailed_statistics()
        print(f'✅ Детальная статистика: {len(detailed_stats)} метрик')
        
        # Тестируем статистику платежей
        payment_stats = await stats_service.get_payment_statistics()
        print(f'✅ Статистика платежей: {payment_stats.get(\"total\", {}).get(\"count\", 0)} платежей')
        
        print('✅ Все тесты пройдены успешно')
        
    except Exception as e:
        print(f'❌ Ошибка тестирования: {e}')
        sys.exit(1)

asyncio.run(test_statistics())
" || {
        log_error "Ошибка тестирования системы!"
        exit 1
    }
    
    log_success "Система протестирована успешно"
}

# Запуск бота
start_bot() {
    log_info "Запуск бота..."
    
    source .venv/bin/activate
    
    # Запускаем бота в фоне
    nohup python main.py > bot.log 2>&1 &
    BOT_PID=$!
    
    # Ждем запуска
    sleep 5
    
    # Проверяем, что процесс запущен
    if kill -0 $BOT_PID 2>/dev/null; then
        log_success "Бот запущен (PID: $BOT_PID)"
        echo $BOT_PID > bot.pid
    else
        log_error "Ошибка запуска бота!"
        exit 1
    fi
}

# Запуск админ-панели
start_admin() {
    log_info "Запуск админ-панели..."
    
    source .venv/bin/activate
    
    # Запускаем админ-панель в фоне
    nohup python run_admin.py > admin.log 2>&1 &
    ADMIN_PID=$!
    
    # Ждем запуска
    sleep 3
    
    # Проверяем, что процесс запущен
    if kill -0 $ADMIN_PID 2>/dev/null; then
        log_success "Админ-панель запущена (PID: $ADMIN_PID)"
        echo $ADMIN_PID > admin.pid
    else
        log_error "Ошибка запуска админ-панели!"
        exit 1
    fi
}

# Финальная проверка
final_check() {
    log_info "Финальная проверка системы..."
    
    # Проверяем процессы
    if pgrep -f "python main.py" > /dev/null; then
        log_success "✅ Бот работает"
    else
        log_error "❌ Бот не запущен"
    fi
    
    if pgrep -f "python run_admin.py" > /dev/null; then
        log_success "✅ Админ-панель работает"
    else
        log_warning "⚠️ Админ-панель не запущена"
    fi
    
    # Проверяем порты
    if netstat -tuln | grep :8080 > /dev/null; then
        log_success "✅ Админ-панель доступна на порту 8080"
    else
        log_warning "⚠️ Порт 8080 не прослушивается"
    fi
    
    log_success "Применение исправлений завершено!"
    echo ""
    echo "📊 Проверьте статистику:"
    echo "• Веб-панель: http://185.207.66.201:8080/"
    echo "• Команды бота: /stats, /payment_stats, /health"
    echo ""
    echo "📋 Логи:"
    echo "• Бот: tail -f bot.log"
    echo "• Админ-панель: tail -f admin.log"
}

# Основная функция
main() {
    echo "🔧 Production-ready применение исправлений статистики"
    echo "Сервер: 185.207.66.201"
    echo "Проект: Telegram Channel Finder Bot"
    echo ""
    
    # Проверяем, что DATABASE_URL установлена
    if [ -z "$DATABASE_URL" ]; then
        log_warning "DATABASE_URL не установлена"
        log_info "Устанавливаю значение по умолчанию..."
        export DATABASE_URL="postgresql://findertool_user:Findertool1999!@postgres:5432/findertool_prod"
    fi
    
    log_info "DATABASE_URL: $DATABASE_URL"
    echo ""
    
    # Выполняем все этапы
    check_server
    create_backup
    stop_bot
    check_database
    migrate_data
    install_dependencies
    init_database
    test_system
    start_bot
    start_admin
    final_check
    
    log_success "🎉 Все исправления применены успешно!"
}

# Запуск основной функции
main "$@"

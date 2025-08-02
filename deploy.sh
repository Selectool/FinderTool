#!/bin/bash

# =============================================================================
# Production Deployment Script для Railpack/Dokploy
# Telegram Channel Finder Bot - Senior Developer уровень
# =============================================================================

set -e  # Выход при любой ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функции для логирования
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

# Проверка окружения
check_environment() {
    log_info "🔍 Проверка окружения для production деплоя..."
    
    # Проверяем Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker не установлен!"
        exit 1
    fi
    
    # Проверяем Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose не установлен!"
        exit 1
    fi
    
    # Проверяем переменные окружения
    if [ -z "$BOT_TOKEN" ]; then
        log_error "BOT_TOKEN не установлен!"
        exit 1
    fi
    
    if [ -z "$POSTGRES_PASSWORD" ]; then
        log_error "POSTGRES_PASSWORD не установлен!"
        exit 1
    fi
    
    log_success "Окружение проверено успешно"
}

# Создание директорий для персистентных данных
create_data_directories() {
    log_info "📁 Создание директорий для персистентных данных..."
    
    # Создаем директории для volumes
    mkdir -p data/postgres
    mkdir -p data/backups
    mkdir -p data/logs
    mkdir -p data/app_backups
    mkdir -p data/uploads
    
    # Устанавливаем правильные права доступа
    chmod 755 data
    chmod 700 data/postgres  # PostgreSQL требует 700
    chmod 755 data/backups
    chmod 755 data/logs
    chmod 755 data/app_backups
    chmod 755 data/uploads
    
    log_success "Директории созданы с правильными правами доступа"
}

# Backup существующих данных
backup_existing_data() {
    if [ -d "data/postgres" ] && [ "$(ls -A data/postgres)" ]; then
        log_info "💾 Создание backup существующих данных..."
        
        BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
        mkdir -p "$BACKUP_DIR"
        
        # Backup PostgreSQL данных
        if [ -d "data/postgres" ]; then
            cp -r data/postgres "$BACKUP_DIR/"
            log_success "PostgreSQL данные сохранены в $BACKUP_DIR"
        fi
        
        # Backup логов
        if [ -d "data/logs" ]; then
            cp -r data/logs "$BACKUP_DIR/"
            log_success "Логи сохранены в $BACKUP_DIR"
        fi
        
        log_success "Backup завершен: $BACKUP_DIR"
    else
        log_info "Существующие данные не найдены, backup не требуется"
    fi
}

# Остановка существующих контейнеров
stop_existing_containers() {
    log_info "🛑 Остановка существующих контейнеров..."
    
    # Останавливаем и удаляем контейнеры
    docker-compose down --remove-orphans || true
    
    # Удаляем старые образы (опционально)
    if [ "$CLEAN_IMAGES" = "true" ]; then
        log_info "🧹 Очистка старых образов..."
        docker image prune -f || true
    fi
    
    log_success "Существующие контейнеры остановлены"
}

# Сборка и запуск production контейнеров
deploy_production() {
    log_info "🚀 Запуск production деплоя..."
    
    # Сборка образов
    log_info "🔨 Сборка Docker образов..."
    docker-compose build --no-cache
    
    # Запуск контейнеров
    log_info "▶️ Запуск контейнеров..."
    docker-compose up -d
    
    log_success "Production контейнеры запущены"
}

# Проверка здоровья сервисов
health_check() {
    log_info "🏥 Проверка здоровья сервисов..."
    
    # Ждем запуска PostgreSQL
    log_info "⏳ Ожидание запуска PostgreSQL..."
    for i in {1..30}; do
        if docker-compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1; then
            log_success "PostgreSQL готов к работе"
            break
        fi
        
        if [ $i -eq 30 ]; then
            log_error "PostgreSQL не запустился за 30 секунд"
            exit 1
        fi
        
        sleep 1
    done
    
    # Ждем запуска основного приложения
    log_info "⏳ Ожидание запуска приложения..."
    for i in {1..60}; do
        if curl -f http://localhost:8000/health > /dev/null 2>&1; then
            log_success "Приложение готово к работе"
            break
        fi
        
        if [ $i -eq 60 ]; then
            log_error "Приложение не запустилось за 60 секунд"
            docker-compose logs telegram-bot
            exit 1
        fi
        
        sleep 1
    done
    
    log_success "Все сервисы работают корректно"
}

# Показать статус деплоя
show_deployment_status() {
    log_info "📊 Статус деплоя:"
    
    echo ""
    echo "🐳 Docker контейнеры:"
    docker-compose ps
    
    echo ""
    echo "🌐 Доступные endpoints:"
    echo "  • Telegram Bot: @FinderTool_bot"
    echo "  • Админ-панель: http://localhost:8000"
    echo "  • Health Check: http://localhost:8000/health"
    echo "  • Metrics: http://localhost:8000/metrics"
    
    echo ""
    echo "📁 Персистентные данные:"
    echo "  • PostgreSQL: $(pwd)/data/postgres"
    echo "  • Логи: $(pwd)/data/logs"
    echo "  • Backups: $(pwd)/data/backups"
    
    echo ""
    log_success "🎉 Production деплой завершен успешно!"
}

# Основная функция
main() {
    echo "============================================================================="
    echo "🚀 PRODUCTION DEPLOYMENT - Telegram Channel Finder Bot"
    echo "🏗️  Платформа: Railpack/Dokploy"
    echo "🗄️  База данных: PostgreSQL (персистентная)"
    echo "============================================================================="
    
    # Проверяем аргументы
    if [ "$1" = "--clean" ]; then
        export CLEAN_IMAGES=true
        log_info "🧹 Режим очистки включен"
    fi
    
    # Выполняем деплой
    check_environment
    create_data_directories
    backup_existing_data
    stop_existing_containers
    deploy_production
    health_check
    show_deployment_status
    
    echo ""
    echo "============================================================================="
    log_success "✅ ДЕПЛОЙ ЗАВЕРШЕН УСПЕШНО!"
    echo "============================================================================="
    
    # Показываем полезные команды
    echo ""
    echo "📋 Полезные команды для управления:"
    echo "  • Просмотр логов:     docker-compose logs -f telegram-bot"
    echo "  • Перезапуск:         docker-compose restart telegram-bot"
    echo "  • Остановка:          docker-compose down"
    echo "  • Backup PostgreSQL:  ./scripts/backup_postgres.sh"
    echo "  • Мониторинг:         docker-compose top"
    echo ""
}

# Обработка сигналов
trap 'log_error "Деплой прерван пользователем"; exit 1' INT TERM

# Запуск
main "$@"

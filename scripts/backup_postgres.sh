#!/bin/bash

# =============================================================================
# PostgreSQL Backup Script для Production
# Автоматическое создание backup с ротацией
# =============================================================================

set -e

# Конфигурация
BACKUP_DIR="data/backups"
POSTGRES_CONTAINER="telegram-bot-postgres"
POSTGRES_DB="telegram_bot"
POSTGRES_USER="postgres"
RETENTION_DAYS=7  # Хранить backup 7 дней

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# Создание backup
create_backup() {
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_file="$BACKUP_DIR/postgres_backup_$timestamp.sql"
    local backup_compressed="$backup_file.gz"
    
    log_info "💾 Создание backup PostgreSQL..."
    log_info "📁 Файл: $backup_compressed"
    
    # Создаем директорию если не существует
    mkdir -p "$BACKUP_DIR"
    
    # Проверяем что контейнер запущен
    if ! docker ps | grep -q "$POSTGRES_CONTAINER"; then
        log_error "Контейнер PostgreSQL не запущен: $POSTGRES_CONTAINER"
        exit 1
    fi
    
    # Создаем backup
    docker exec "$POSTGRES_CONTAINER" pg_dump \
        -U "$POSTGRES_USER" \
        -d "$POSTGRES_DB" \
        --verbose \
        --clean \
        --if-exists \
        --create \
        --format=plain > "$backup_file"
    
    # Сжимаем backup
    gzip "$backup_file"
    
    # Проверяем размер
    local size=$(du -h "$backup_compressed" | cut -f1)
    log_success "Backup создан: $backup_compressed ($size)"
    
    echo "$backup_compressed"
}

# Очистка старых backup
cleanup_old_backups() {
    log_info "🧹 Очистка старых backup (старше $RETENTION_DAYS дней)..."
    
    local deleted_count=0
    
    # Находим и удаляем старые файлы
    find "$BACKUP_DIR" -name "postgres_backup_*.sql.gz" -type f -mtime +$RETENTION_DAYS -print0 | \
    while IFS= read -r -d '' file; do
        log_info "Удаляем старый backup: $(basename "$file")"
        rm "$file"
        ((deleted_count++))
    done
    
    if [ $deleted_count -gt 0 ]; then
        log_success "Удалено $deleted_count старых backup"
    else
        log_info "Старые backup не найдены"
    fi
}

# Проверка backup
verify_backup() {
    local backup_file="$1"
    
    log_info "✅ Проверка целостности backup..."
    
    # Проверяем что файл существует и не пустой
    if [ ! -f "$backup_file" ] || [ ! -s "$backup_file" ]; then
        log_error "Backup файл поврежден или пустой"
        return 1
    fi
    
    # Проверяем что это валидный gzip файл
    if ! gzip -t "$backup_file" 2>/dev/null; then
        log_error "Backup файл поврежден (не валидный gzip)"
        return 1
    fi
    
    # Проверяем содержимое
    local content_check=$(zcat "$backup_file" | head -n 10 | grep -c "PostgreSQL database dump" || true)
    if [ "$content_check" -eq 0 ]; then
        log_error "Backup файл не содержит валидный PostgreSQL dump"
        return 1
    fi
    
    log_success "Backup прошел проверку целостности"
    return 0
}

# Восстановление из backup
restore_backup() {
    local backup_file="$1"
    
    if [ -z "$backup_file" ]; then
        log_error "Не указан файл backup для восстановления"
        echo "Использование: $0 restore <backup_file>"
        exit 1
    fi
    
    if [ ! -f "$backup_file" ]; then
        log_error "Backup файл не найден: $backup_file"
        exit 1
    fi
    
    log_warning "⚠️  ВНИМАНИЕ: Восстановление удалит все текущие данные!"
    read -p "Продолжить? (yes/no): " confirm
    
    if [ "$confirm" != "yes" ]; then
        log_info "Восстановление отменено"
        exit 0
    fi
    
    log_info "🔄 Восстановление из backup: $backup_file"
    
    # Останавливаем приложение
    log_info "Остановка приложения..."
    docker-compose stop telegram-bot || true
    
    # Восстанавливаем данные
    log_info "Восстановление данных..."
    zcat "$backup_file" | docker exec -i "$POSTGRES_CONTAINER" psql -U "$POSTGRES_USER"
    
    # Запускаем приложение
    log_info "Запуск приложения..."
    docker-compose start telegram-bot
    
    log_success "Восстановление завершено"
}

# Список доступных backup
list_backups() {
    log_info "📋 Доступные backup:"
    
    if [ ! -d "$BACKUP_DIR" ]; then
        log_warning "Директория backup не найдена: $BACKUP_DIR"
        return
    fi
    
    local backups=($(find "$BACKUP_DIR" -name "postgres_backup_*.sql.gz" -type f | sort -r))
    
    if [ ${#backups[@]} -eq 0 ]; then
        log_warning "Backup файлы не найдены"
        return
    fi
    
    echo ""
    printf "%-30s %-10s %-20s\n" "ФАЙЛ" "РАЗМЕР" "ДАТА"
    echo "================================================================"
    
    for backup in "${backups[@]}"; do
        local filename=$(basename "$backup")
        local size=$(du -h "$backup" | cut -f1)
        local date=$(stat -c %y "$backup" | cut -d' ' -f1,2 | cut -d'.' -f1)
        printf "%-30s %-10s %-20s\n" "$filename" "$size" "$date"
    done
    
    echo ""
}

# Автоматический backup (для cron)
auto_backup() {
    log_info "🤖 Автоматический backup..."
    
    # Создаем backup
    local backup_file=$(create_backup)
    
    # Проверяем backup
    if verify_backup "$backup_file"; then
        # Очищаем старые backup
        cleanup_old_backups
        
        log_success "Автоматический backup завершен успешно"
    else
        log_error "Автоматический backup провален"
        exit 1
    fi
}

# Показать помощь
show_help() {
    echo "PostgreSQL Backup Script для Telegram Channel Finder Bot"
    echo ""
    echo "Использование:"
    echo "  $0 create                    - Создать backup"
    echo "  $0 restore <backup_file>     - Восстановить из backup"
    echo "  $0 list                      - Показать доступные backup"
    echo "  $0 cleanup                   - Очистить старые backup"
    echo "  $0 auto                      - Автоматический backup (для cron)"
    echo "  $0 help                      - Показать эту справку"
    echo ""
    echo "Примеры:"
    echo "  $0 create"
    echo "  $0 restore data/backups/postgres_backup_20250101_120000.sql.gz"
    echo "  $0 list"
    echo ""
}

# Основная функция
main() {
    case "${1:-help}" in
        "create")
            backup_file=$(create_backup)
            verify_backup "$backup_file"
            ;;
        "restore")
            restore_backup "$2"
            ;;
        "list")
            list_backups
            ;;
        "cleanup")
            cleanup_old_backups
            ;;
        "auto")
            auto_backup
            ;;
        "help"|*)
            show_help
            ;;
    esac
}

# Запуск
main "$@"

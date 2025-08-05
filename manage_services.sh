#!/bin/bash

# Скрипт для управления службами Telegram бота и админ-панели
# Автор: Джарвис AI Assistant

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функция для вывода цветного текста
print_status() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Функция проверки статуса службы
check_service() {
    local service=$1
    if systemctl is-active --quiet $service; then
        print_status $GREEN "✅ $service: АКТИВНА"
        return 0
    else
        print_status $RED "❌ $service: НЕАКТИВНА"
        return 1
    fi
}

# Функция показа статуса всех служб
show_status() {
    print_status $BLUE "📊 СТАТУС СЛУЖБ"
    echo "===================="
    check_service telegram-bot.service
    check_service admin-panel.service
    echo ""
    
    print_status $BLUE "🔍 ДЕТАЛЬНАЯ ИНФОРМАЦИЯ"
    echo "========================"
    systemctl status telegram-bot.service --no-pager -l | head -10
    echo ""
    systemctl status admin-panel.service --no-pager -l | head -10
    echo ""
    
    print_status $BLUE "🌐 СЕТЕВЫЕ ПОРТЫ"
    echo "=================="
    ss -tulpn | grep :8080 || print_status $YELLOW "⚠️ Порт 8080 не прослушивается"
}

# Функция перезапуска всех служб
restart_all() {
    print_status $YELLOW "🔄 Перезапуск всех служб..."
    systemctl restart telegram-bot.service
    systemctl restart admin-panel.service
    sleep 3
    show_status
}

# Функция остановки всех служб
stop_all() {
    print_status $YELLOW "⏹️ Остановка всех служб..."
    systemctl stop telegram-bot.service
    systemctl stop admin-panel.service
    show_status
}

# Функция запуска всех служб
start_all() {
    print_status $YELLOW "▶️ Запуск всех служб..."
    systemctl start telegram-bot.service
    systemctl start admin-panel.service
    sleep 3
    show_status
}

# Функция показа логов
show_logs() {
    local service=$1
    if [ -z "$service" ]; then
        print_status $BLUE "📋 ПОСЛЕДНИЕ ЛОГИ TELEGRAM BOT"
        echo "==============================="
        journalctl -u telegram-bot.service --no-pager -n 20
        echo ""
        print_status $BLUE "📋 ПОСЛЕДНИЕ ЛОГИ ADMIN PANEL"
        echo "=============================="
        journalctl -u admin-panel.service --no-pager -n 20
    else
        print_status $BLUE "📋 ЛОГИ $service"
        journalctl -u $service --no-pager -n 50
    fi
}

# Функция показа помощи
show_help() {
    echo "🤖 Управление службами Telegram Channel Finder Bot"
    echo "=================================================="
    echo ""
    echo "Использование: $0 [команда]"
    echo ""
    echo "Команды:"
    echo "  status     - Показать статус всех служб (по умолчанию)"
    echo "  start      - Запустить все службы"
    echo "  stop       - Остановить все службы"
    echo "  restart    - Перезапустить все службы"
    echo "  logs       - Показать последние логи всех служб"
    echo "  logs-bot   - Показать логи только Telegram бота"
    echo "  logs-admin - Показать логи только админ-панели"
    echo "  help       - Показать эту справку"
    echo ""
    echo "Примеры:"
    echo "  $0                    # Показать статус"
    echo "  $0 restart           # Перезапустить все службы"
    echo "  $0 logs-bot          # Показать логи бота"
    echo ""
    echo "Полезные команды systemctl:"
    echo "  systemctl status telegram-bot.service"
    echo "  systemctl restart admin-panel.service"
    echo "  journalctl -u telegram-bot.service -f"
}

# Основная логика
case "${1:-status}" in
    "status")
        show_status
        ;;
    "start")
        start_all
        ;;
    "stop")
        stop_all
        ;;
    "restart")
        restart_all
        ;;
    "logs")
        show_logs
        ;;
    "logs-bot")
        show_logs "telegram-bot.service"
        ;;
    "logs-admin")
        show_logs "admin-panel.service"
        ;;
    "help"|"-h"|"--help")
        show_help
        ;;
    *)
        print_status $RED "❌ Неизвестная команда: $1"
        echo ""
        show_help
        exit 1
        ;;
esac

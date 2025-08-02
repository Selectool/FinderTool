#!/bin/bash

# Professional Supervisor startup для production
echo "🚀 Запуск Telegram Channel Finder Bot с Supervisor (Production)"

# Устанавливаем переменные окружения
export ENVIRONMENT=production
export DEBIAN_FRONTEND=noninteractive
export PYTHONPATH=/app
export PYTHONUNBUFFERED=1

# Функция для установки supervisor
install_supervisor() {
    echo "📦 Проверка и установка Supervisor..."
    
    if command -v supervisord &> /dev/null; then
        echo "✅ Supervisor уже установлен"
        supervisord --version
        return 0
    fi
    
    echo "📥 Обновление пакетов..."
    apt-get update -qq
    
    echo "📦 Установка Supervisor..."
    apt-get install -y supervisor
    
    if command -v supervisord &> /dev/null; then
        echo "✅ Supervisor установлен успешно"
        supervisord --version
        return 0
    else
        echo "❌ Ошибка установки Supervisor"
        return 1
    fi
}

# Функция для создания оптимизированной конфигурации
create_optimized_config() {
    echo "📝 Создание оптимизированной конфигурации Supervisor..."
    
    # Создаем необходимые директории
    mkdir -p /var/log/supervisor
    mkdir -p /var/run
    mkdir -p /etc/supervisor/conf.d
    
    # Создаем конфигурацию с исправленными настройками
    cat > /etc/supervisor/conf.d/findertool_production.conf << 'EOF'
[supervisord]
nodaemon=true
user=root
logfile=/var/log/supervisor/supervisord.log
pidfile=/var/run/supervisord.pid
childlogdir=/var/log/supervisor
loglevel=info
silent=false

[unix_http_server]
file=/var/run/supervisor.sock
chmod=0700

[supervisorctl]
serverurl=unix:///var/run/supervisor.sock

[rpcinterface:supervisor]
supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface

[program:telegram_bot]
command=python main.py
directory=/app
autostart=true
autorestart=true
startretries=5
startsecs=10
user=root
redirect_stderr=true
stdout_logfile=/var/log/supervisor/telegram_bot.log
stdout_logfile_maxbytes=100MB
stdout_logfile_backups=5
stderr_logfile=/var/log/supervisor/telegram_bot_error.log
stderr_logfile_maxbytes=100MB
stderr_logfile_backups=5
environment=ENVIRONMENT=production,PYTHONPATH=/app,PYTHONUNBUFFERED=1
priority=100

[program:admin_panel]
command=python run_admin.py
directory=/app
autostart=true
autorestart=true
startretries=5
startsecs=10
user=root
redirect_stderr=true
stdout_logfile=/var/log/supervisor/admin_panel.log
stdout_logfile_maxbytes=100MB
stdout_logfile_backups=5
stderr_logfile=/var/log/supervisor/admin_panel_error.log
stderr_logfile_maxbytes=100MB
stderr_logfile_backups=5
environment=ENVIRONMENT=production,ADMIN_ALLOWED_HOSTS="185.207.66.201,findertool.dokploy.com,localhost,127.0.0.1,0.0.0.0",ADMIN_CORS_ORIGINS="http://185.207.66.201:8080,https://findertool.dokploy.com,http://localhost:8080,http://127.0.0.1:8080",ADMIN_HOST=0.0.0.0,ADMIN_PORT=8080,PYTHONPATH=/app,PYTHONUNBUFFERED=1
priority=200

[group:findertool_services]
programs=telegram_bot,admin_panel
priority=999
EOF

    echo "✅ Оптимизированная конфигурация создана"
}

# Функция для запуска сервисов
start_supervisor_services() {
    echo "🔄 Запуск Supervisor с оптимизированной конфигурацией..."
    
    # Останавливаем существующие процессы
    pkill -f supervisord 2>/dev/null || true
    pkill -f "python main.py" 2>/dev/null || true
    pkill -f "python run_admin.py" 2>/dev/null || true
    
    sleep 3
    
    # Запускаем supervisor
    supervisord -c /etc/supervisor/conf.d/findertool_production.conf &
    
    # Ждем запуска
    sleep 10
    
    # Проверяем статус
    if supervisorctl -c /etc/supervisor/conf.d/findertool_production.conf status > /dev/null 2>&1; then
        echo "✅ Supervisor запущен успешно"
        echo ""
        echo "📊 Статус сервисов:"
        supervisorctl -c /etc/supervisor/conf.d/findertool_production.conf status
        echo ""
        echo "🌐 Админ-панель: http://185.207.66.201:8080"
        echo "🔑 Логин: admin / admin123"
        echo "📋 Команды управления:"
        echo "  • supervisorctl status - статус сервисов"
        echo "  • supervisorctl restart telegram_bot - перезапуск бота"
        echo "  • supervisorctl restart admin_panel - перезапуск админки"
        echo "  • supervisorctl tail -f telegram_bot - логи бота"
        echo "  • supervisorctl tail -f admin_panel - логи админки"
        echo ""
        return 0
    else
        echo "❌ Ошибка запуска Supervisor"
        echo "📋 Проверьте логи:"
        echo "  • cat /var/log/supervisor/supervisord.log"
        echo "  • cat /var/log/supervisor/telegram_bot.log"
        echo "  • cat /var/log/supervisor/admin_panel.log"
        return 1
    fi
}

# Функция для мониторинга
monitor_services() {
    echo "📊 Запуск мониторинга сервисов..."
    
    # Функция для graceful shutdown
    cleanup() {
        echo ""
        echo "🛑 Остановка сервисов..."
        supervisorctl -c /etc/supervisor/conf.d/findertool_production.conf stop all
        pkill -f supervisord
        echo "✅ Все сервисы остановлены"
        exit 0
    }
    
    # Устанавливаем обработчики сигналов
    trap cleanup SIGTERM SIGINT
    
    # Мониторинг
    while true; do
        sleep 60
        
        # Получаем статус
        STATUS_OUTPUT=$(supervisorctl -c /etc/supervisor/conf.d/findertool_production.conf status 2>/dev/null)
        
        if [ $? -eq 0 ]; then
            BOT_STATUS=$(echo "$STATUS_OUTPUT" | grep telegram_bot | awk '{print $2}')
            ADMIN_STATUS=$(echo "$STATUS_OUTPUT" | grep admin_panel | awk '{print $2}')
            
            TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
            echo "$TIMESTAMP - Bot: $BOT_STATUS, Admin: $ADMIN_STATUS"
            
            # Если оба сервиса не работают
            if [[ "$BOT_STATUS" != "RUNNING" && "$ADMIN_STATUS" != "RUNNING" ]]; then
                echo "❌ Все сервисы остановлены"
                break
            fi
            
            # Показываем дополнительную информацию каждые 5 минут
            if [ $(($(date +%M) % 5)) -eq 0 ] && [ $(date +%S) -lt 60 ]; then
                echo "📊 Подробный статус:"
                supervisorctl -c /etc/supervisor/conf.d/findertool_production.conf status
                echo "💾 Использование памяти:"
                ps aux | grep -E "(python main.py|python run_admin.py)" | grep -v grep
                echo ""
            fi
        else
            echo "⚠️ Ошибка получения статуса сервисов"
        fi
    done
    
    cleanup
}

# Основная логика
main() {
    echo "🏁 Начало установки и запуска с Supervisor..."
    
    # Переходим в рабочую директорию
    cd /app || { echo "❌ Директория /app не найдена"; exit 1; }
    
    # Устанавливаем supervisor
    if ! install_supervisor; then
        echo "❌ Не удалось установить Supervisor"
        exit 1
    fi
    
    # Создаем оптимизированную конфигурацию
    create_optimized_config
    
    # Запускаем сервисы
    if ! start_supervisor_services; then
        echo "❌ Не удалось запустить сервисы"
        exit 1
    fi
    
    # Запускаем мониторинг
    monitor_services
}

# Запуск
main "$@"

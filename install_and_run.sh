#!/bin/bash

# Универсальный скрипт установки и запуска для Dokploy/Railpack
echo "🚀 Telegram Channel Finder Bot - Production Setup"

# Устанавливаем переменные окружения
export ENVIRONMENT=production
export DEBIAN_FRONTEND=noninteractive

# Функция для установки supervisor
install_supervisor() {
    echo "📦 Проверка и установка Supervisor..."
    
    if command -v supervisord &> /dev/null; then
        echo "✅ Supervisor уже установлен"
        return 0
    fi
    
    echo "📥 Обновление пакетов..."
    apt-get update -qq
    
    echo "📦 Установка Supervisor..."
    apt-get install -y supervisor
    
    if command -v supervisord &> /dev/null; then
        echo "✅ Supervisor установлен успешно"
        return 0
    else
        echo "❌ Ошибка установки Supervisor"
        return 1
    fi
}

# Функция для создания конфигурации
create_supervisor_config() {
    echo "📝 Создание конфигурации Supervisor..."
    
    mkdir -p /var/log/supervisor
    mkdir -p /var/run
    
    cat > /etc/supervisor/conf.d/findertool.conf << 'EOF'
[supervisord]
nodaemon=true
user=root
logfile=/var/log/supervisor/supervisord.log
pidfile=/var/run/supervisord.pid
childlogdir=/var/log/supervisor
loglevel=info

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
startretries=3
user=root
redirect_stderr=true
stdout_logfile=/var/log/supervisor/telegram_bot.log
stdout_logfile_maxbytes=50MB
stdout_logfile_backups=10
environment=ENVIRONMENT=production

[program:admin_panel]
command=python run_admin.py
directory=/app
autostart=true
autorestart=true
startretries=3
user=root
redirect_stderr=true
stdout_logfile=/var/log/supervisor/admin_panel.log
stdout_logfile_maxbytes=50MB
stdout_logfile_backups=10
environment=ENVIRONMENT=production
priority=999

[group:findertool_services]
programs=telegram_bot,admin_panel
priority=999
EOF

    echo "✅ Конфигурация создана"
}

# Функция для запуска сервисов
start_services() {
    echo "🔄 Запуск сервисов..."
    
    # Запускаем supervisor
    supervisord -c /etc/supervisor/conf.d/findertool.conf &
    
    # Ждем запуска
    sleep 5
    
    # Проверяем статус
    if supervisorctl status > /dev/null 2>&1; then
        echo "✅ Сервисы запущены успешно"
        echo ""
        echo "📊 Статус сервисов:"
        supervisorctl status
        echo ""
        echo "🌐 Админ-панель: http://0.0.0.0:8080"
        echo "📋 Логи бота: tail -f /var/log/supervisor/telegram_bot.log"
        echo "📋 Логи админ-панели: tail -f /var/log/supervisor/admin_panel.log"
        echo ""
        return 0
    else
        echo "❌ Ошибка запуска сервисов"
        return 1
    fi
}

# Функция для мониторинга
monitor_services() {
    echo "📊 Запуск мониторинга..."
    
    # Функция для graceful shutdown
    cleanup() {
        echo ""
        echo "🛑 Остановка сервисов..."
        supervisorctl stop all
        supervisord shutdown
        echo "✅ Все сервисы остановлены"
        exit 0
    }
    
    # Устанавливаем обработчики сигналов
    trap cleanup SIGTERM SIGINT
    
    # Мониторинг
    while true; do
        sleep 30
        
        # Получаем статус
        STATUS_OUTPUT=$(supervisorctl status 2>/dev/null)
        
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
        else
            echo "⚠️ Ошибка получения статуса сервисов"
        fi
    done
    
    cleanup
}

# Основная логика
main() {
    echo "🏁 Начало установки и запуска..."
    
    # Переходим в рабочую директорию
    cd /app || { echo "❌ Директория /app не найдена"; exit 1; }
    
    # Устанавливаем supervisor
    if ! install_supervisor; then
        echo "❌ Не удалось установить Supervisor"
        exit 1
    fi
    
    # Создаем конфигурацию
    create_supervisor_config
    
    # Запускаем сервисы
    if ! start_services; then
        echo "❌ Не удалось запустить сервисы"
        exit 1
    fi
    
    # Запускаем мониторинг
    monitor_services
}

# Запуск
main "$@"

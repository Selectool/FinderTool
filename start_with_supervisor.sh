#!/bin/bash

# Professional startup script с Supervisor для production
echo "🚀 Запуск Telegram Channel Finder Bot с Supervisor..."

# Устанавливаем переменные окружения
export ENVIRONMENT=production
export PYTHONPATH=/app
export PYTHONUNBUFFERED=1

# Проверяем наличие supervisor
if ! command -v supervisord &> /dev/null; then
    echo "📦 Установка Supervisor..."
    apt-get update && apt-get install -y supervisor
fi

# Создаем необходимые директории
mkdir -p /var/log/supervisor
mkdir -p /var/run

# Создаем конфигурацию supervisor на лету
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
environment=ENVIRONMENT=production,PYTHONPATH=/app,PYTHONUNBUFFERED=1

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
environment=ENVIRONMENT=production,PYTHONPATH=/app,PYTHONUNBUFFERED=1
priority=999

[group:findertool_services]
programs=telegram_bot,admin_panel
priority=999
EOF

echo "✅ Конфигурация Supervisor создана"

# Функция для отображения статуса
show_status() {
    echo ""
    echo "📊 Статус сервисов:"
    supervisorctl status
    echo ""
    echo "🌐 Админ-панель: http://0.0.0.0:8080"
    echo "📋 Логи бота: tail -f /var/log/supervisor/telegram_bot.log"
    echo "📋 Логи админ-панели: tail -f /var/log/supervisor/admin_panel.log"
    echo "🔧 Управление: supervisorctl [start|stop|restart] [telegram_bot|admin_panel]"
}

# Функция для graceful shutdown
cleanup() {
    echo ""
    echo "🛑 Получен сигнал остановки..."
    supervisorctl stop all
    supervisord shutdown
    echo "✅ Все сервисы остановлены"
    exit 0
}

# Устанавливаем обработчики сигналов
trap cleanup SIGTERM SIGINT

echo "🔄 Запуск Supervisor..."

# Запускаем supervisor
supervisord -c /etc/supervisor/conf.d/findertool.conf &

# Ждем запуска supervisor
sleep 3

# Проверяем статус
if supervisorctl status > /dev/null 2>&1; then
    echo "✅ Supervisor запущен успешно"
    show_status
    
    # Мониторинг в реальном времени
    echo "📊 Мониторинг сервисов (Ctrl+C для остановки)..."
    
    while true; do
        sleep 30
        
        # Проверяем статус сервисов
        BOT_STATUS=$(supervisorctl status telegram_bot | awk '{print $2}')
        ADMIN_STATUS=$(supervisorctl status admin_panel | awk '{print $2}')
        
        echo "$(date '+%Y-%m-%d %H:%M:%S') - Bot: $BOT_STATUS, Admin: $ADMIN_STATUS"
        
        # Если оба сервиса не работают, выходим
        if [[ "$BOT_STATUS" != "RUNNING" && "$ADMIN_STATUS" != "RUNNING" ]]; then
            echo "❌ Все сервисы остановлены"
            break
        fi
    done
else
    echo "❌ Ошибка запуска Supervisor"
    exit 1
fi

cleanup

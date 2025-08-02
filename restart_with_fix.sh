#!/bin/bash

echo "🔧 Перезапуск с исправленными настройками хостов..."

# Останавливаем текущие процессы
echo "🛑 Остановка текущих сервисов..."
supervisorctl stop all 2>/dev/null || true
pkill -f supervisord 2>/dev/null || true
pkill -f "python main.py" 2>/dev/null || true
pkill -f "python run_admin.py" 2>/dev/null || true

sleep 3

# Устанавливаем переменные окружения
export ENVIRONMENT=production
export ADMIN_ALLOWED_HOSTS="*"
export ADMIN_CORS_ORIGINS="*"
export ADMIN_HOST="0.0.0.0"
export ADMIN_PORT="8080"

echo "✅ Переменные окружения установлены:"
echo "   ADMIN_ALLOWED_HOSTS: $ADMIN_ALLOWED_HOSTS"
echo "   ADMIN_CORS_ORIGINS: $ADMIN_CORS_ORIGINS"
echo "   ADMIN_HOST: $ADMIN_HOST"
echo "   ADMIN_PORT: $ADMIN_PORT"

# Создаем исправленную конфигурацию
cat > /etc/supervisor/conf.d/findertool_fixed.conf << 'EOF'
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
environment=ENVIRONMENT=production,ADMIN_ALLOWED_HOSTS=*,ADMIN_CORS_ORIGINS=*,ADMIN_HOST=0.0.0.0,ADMIN_PORT=8080
priority=999

[group:findertool_services]
programs=telegram_bot,admin_panel
priority=999
EOF

echo "✅ Исправленная конфигурация создана"

# Запускаем supervisor с новой конфигурацией
echo "🔄 Запуск Supervisor с исправленными настройками..."
supervisord -c /etc/supervisor/conf.d/findertool_fixed.conf &

# Ждем запуска
sleep 5

# Проверяем статус
if supervisorctl status > /dev/null 2>&1; then
    echo "✅ Сервисы перезапущены успешно"
    echo ""
    echo "📊 Статус сервисов:"
    supervisorctl status
    echo ""
    echo "🌐 Админ-панель: http://185.207.66.201:8080"
    echo "🔧 Настройки хостов исправлены - теперь разрешены все хосты"
    echo ""
    
    # Мониторинг
    while true; do
        sleep 30
        STATUS_OUTPUT=$(supervisorctl status 2>/dev/null)
        if [ $? -eq 0 ]; then
            BOT_STATUS=$(echo "$STATUS_OUTPUT" | grep telegram_bot | awk '{print $2}')
            ADMIN_STATUS=$(echo "$STATUS_OUTPUT" | grep admin_panel | awk '{print $2}')
            TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
            echo "$TIMESTAMP - Bot: $BOT_STATUS, Admin: $ADMIN_STATUS"
        fi
    done
else
    echo "❌ Ошибка перезапуска сервисов"
    exit 1
fi

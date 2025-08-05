#!/bin/bash

# Скрипт для настройки автоматического запуска Telegram бота и админ-панели
# Автор: Джарвис AI Assistant
# Дата: 03.08.2025

set -e

echo "🚀 Настройка автоматического запуска приложений..."

# Проверяем, что мы в правильной директории
if [ ! -f "/app/main.py" ] || [ ! -f "/app/run_admin.py" ]; then
    echo "❌ Ошибка: файлы main.py или run_admin.py не найдены в /app"
    exit 1
fi

# Проверяем виртуальное окружение
if [ ! -d "/app/.venv" ]; then
    echo "❌ Ошибка: виртуальное окружение не найдено в /app/.venv"
    exit 1
fi

echo "✅ Проверки пройдены успешно"

# Создаем systemd service для Telegram бота
echo "📝 Создание службы telegram-bot..."
cat > /etc/systemd/system/telegram-bot.service << 'EOF'
[Unit]
Description=Telegram Channel Finder Bot
After=network.target postgresql.service
Wants=postgresql.service
StartLimitIntervalSec=0

[Service]
Type=simple
Restart=always
RestartSec=10
User=root
WorkingDirectory=/app
Environment=PATH=/app/.venv/bin
ExecStart=/app/.venv/bin/python main.py
StandardOutput=journal
StandardError=journal
SyslogIdentifier=telegram-bot

# Настройки безопасности
NoNewPrivileges=true
PrivateTmp=true

# Настройки ресурсов
MemoryMax=512M
CPUQuota=50%

[Install]
WantedBy=multi-user.target
EOF

# Создаем systemd service для админ-панели
echo "📝 Создание службы admin-panel..."
cat > /etc/systemd/system/admin-panel.service << 'EOF'
[Unit]
Description=Telegram Bot Admin Panel
After=network.target postgresql.service
Wants=postgresql.service
StartLimitIntervalSec=0

[Service]
Type=simple
Restart=always
RestartSec=10
User=root
WorkingDirectory=/app
Environment=PATH=/app/.venv/bin
ExecStart=/app/.venv/bin/python run_admin.py
StandardOutput=journal
StandardError=journal
SyslogIdentifier=admin-panel

# Настройки безопасности
NoNewPrivileges=true
PrivateTmp=true

# Настройки ресурсов
MemoryMax=512M
CPUQuota=50%

[Install]
WantedBy=multi-user.target
EOF

# Перезагружаем systemd
echo "🔄 Перезагрузка systemd..."
systemctl daemon-reload

# Включаем автозапуск служб
echo "🔧 Включение автозапуска служб..."
systemctl enable telegram-bot.service
systemctl enable admin-panel.service

# Запускаем службы
echo "▶️ Запуск служб..."
systemctl start telegram-bot.service
systemctl start admin-panel.service

# Проверяем статус
echo "📊 Проверка статуса служб..."
echo ""
echo "=== TELEGRAM BOT ==="
systemctl status telegram-bot.service --no-pager -l
echo ""
echo "=== ADMIN PANEL ==="
systemctl status admin-panel.service --no-pager -l

echo ""
echo "🎉 Настройка завершена!"
echo ""
echo "📋 Полезные команды для управления службами:"
echo "   systemctl status telegram-bot.service    # Статус бота"
echo "   systemctl status admin-panel.service     # Статус админ-панели"
echo "   systemctl restart telegram-bot.service   # Перезапуск бота"
echo "   systemctl restart admin-panel.service    # Перезапуск админ-панели"
echo "   systemctl stop telegram-bot.service      # Остановка бота"
echo "   systemctl stop admin-panel.service       # Остановка админ-панели"
echo "   journalctl -u telegram-bot.service -f    # Логи бота в реальном времени"
echo "   journalctl -u admin-panel.service -f     # Логи админ-панели в реальном времени"
echo ""
echo "🔍 Проверка портов:"
echo "   ss -tulpn | grep :8080                   # Проверка порта админ-панели"
echo ""

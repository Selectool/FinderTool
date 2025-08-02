#!/bin/bash

# Production startup script для Dokploy
echo "🚀 Запуск Telegram Channel Finder Bot..."

# Устанавливаем переменные окружения
export ENVIRONMENT=production

# Функция для остановки процессов
cleanup() {
    echo "🛑 Останавливаем сервисы..."
    if [ ! -z "$BOT_PID" ]; then
        kill $BOT_PID 2>/dev/null
    fi
    if [ ! -z "$ADMIN_PID" ]; then
        kill $ADMIN_PID 2>/dev/null
    fi
    exit 0
}

# Обработчики сигналов
trap cleanup SIGTERM SIGINT

# Запускаем бота в фоне
echo "🤖 Запуск бота..."
python main.py &
BOT_PID=$!

# Ждем инициализации бота
sleep 10

# Запускаем админ-панель в фоне  
echo "🌐 Запуск админ-панели..."
python run_admin.py &
ADMIN_PID=$!

echo "✅ Сервисы запущены!"
echo "🤖 Бот PID: $BOT_PID"
echo "🌐 Админ PID: $ADMIN_PID"
echo "🌐 Админ-панель: http://0.0.0.0:8080"

# Ждем завершения любого процесса
wait

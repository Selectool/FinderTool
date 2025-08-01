#!/bin/bash
set -e

echo "🚀 Запуск Telegram Channel Finder Bot..."

# Функция для корректного завершения
cleanup() {
    echo "🛑 Получен сигнал завершения..."
    echo "⏹️ Остановка всех процессов..."
    kill $(jobs -p) 2>/dev/null || true
    echo "✅ Все процессы остановлены"
    exit 0
}

# Обработка сигналов
trap cleanup SIGTERM SIGINT

# Запуск бота в фоне
echo "📱 Запуск Telegram бота..."
python main.py &
BOT_PID=$!
echo "✅ Telegram бот запущен (PID: $BOT_PID)"

# Небольшая задержка
sleep 3

# Запуск админ-панели
echo "🌐 Запуск админ-панели..."
python run_admin.py &
ADMIN_PID=$!
echo "✅ Админ-панель запущена (PID: $ADMIN_PID)"

echo "🎉 Все сервисы запущены успешно!"
echo "📱 Telegram бот: PID $BOT_PID"
echo "🌐 Админ-панель: http://localhost:8080 (PID $ADMIN_PID)"

# Ожидание завершения процессов
wait

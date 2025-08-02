#!/bin/bash
# Production startup script для Telegram Channel Finder Bot

echo "🚀 Запуск Telegram Channel Finder Bot в продакшн режиме..."

# Устанавливаем переменные окружения
export ENVIRONMENT=production

# Функция для graceful shutdown
cleanup() {
    echo "🛑 Получен сигнал остановки..."
    kill $BOT_PID $ADMIN_PID 2>/dev/null
    wait $BOT_PID $ADMIN_PID 2>/dev/null
    echo "✅ Все процессы остановлены"
    exit 0
}

# Устанавливаем обработчики сигналов
trap cleanup SIGTERM SIGINT

# Запускаем бота в фоне
echo "🤖 Запуск Telegram бота..."
python main.py &
BOT_PID=$!
echo "✅ Бот запущен (PID: $BOT_PID)"

# Ждем немного для инициализации бота
sleep 5

# Запускаем админ-панель в фоне
echo "🌐 Запуск админ-панели..."
python run_admin.py &
ADMIN_PID=$!
echo "✅ Админ-панель запущена (PID: $ADMIN_PID)"

echo "🎉 Все сервисы запущены!"
echo "🤖 Telegram бот: активен"
echo "🌐 Админ-панель: http://0.0.0.0:8080"
echo "📊 Для остановки используйте Ctrl+C"

# Ждем завершения любого из процессов
wait $BOT_PID $ADMIN_PID

# Если один из процессов завершился, останавливаем остальные
echo "⚠️  Один из процессов завершился, останавливаем остальные..."
cleanup

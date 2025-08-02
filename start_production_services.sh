#!/bin/bash

# Production startup script для запуска бота и админ-панели
echo "🚀 Запуск Telegram Channel Finder Bot + Admin Panel..."

# Устанавливаем переменные окружения
export ENVIRONMENT=production

# Создаем директории для логов
mkdir -p /tmp/logs

# Функция для остановки процессов
cleanup() {
    echo "🛑 Останавливаем сервисы..."
    if [ ! -z "$BOT_PID" ]; then
        kill $BOT_PID 2>/dev/null
        echo "🤖 Бот остановлен"
    fi
    if [ ! -z "$ADMIN_PID" ]; then
        kill $ADMIN_PID 2>/dev/null
        echo "🌐 Админ-панель остановлена"
    fi
    echo "✅ Все сервисы остановлены"
    exit 0
}

# Обработчики сигналов
trap cleanup SIGTERM SIGINT

# Функция для мониторинга процесса
monitor_process() {
    local pid=$1
    local name=$2
    
    while kill -0 $pid 2>/dev/null; do
        sleep 5
    done
    
    echo "❌ $name завершился неожиданно (PID: $pid)"
}

# Запускаем бота в фоне с логированием
echo "🤖 Запуск Telegram бота..."
python main.py > /tmp/logs/bot.log 2>&1 &
BOT_PID=$!

if [ $? -eq 0 ]; then
    echo "✅ Бот запущен (PID: $BOT_PID)"
else
    echo "❌ Ошибка запуска бота"
    exit 1
fi

# Ждем инициализации бота
echo "⏳ Ожидание инициализации бота..."
sleep 15

# Проверяем, что бот все еще работает
if ! kill -0 $BOT_PID 2>/dev/null; then
    echo "❌ Бот завершился во время инициализации"
    echo "📋 Последние строки лога бота:"
    tail -10 /tmp/logs/bot.log
    exit 1
fi

# Запускаем админ-панель в фоне с логированием
echo "🌐 Запуск админ-панели..."
python run_admin.py > /tmp/logs/admin.log 2>&1 &
ADMIN_PID=$!

if [ $? -eq 0 ]; then
    echo "✅ Админ-панель запущена (PID: $ADMIN_PID)"
else
    echo "❌ Ошибка запуска админ-панели"
    kill $BOT_PID 2>/dev/null
    exit 1
fi

# Ждем инициализации админ-панели
echo "⏳ Ожидание инициализации админ-панели..."
sleep 10

# Проверяем, что админ-панель работает
if ! kill -0 $ADMIN_PID 2>/dev/null; then
    echo "❌ Админ-панель завершилась во время инициализации"
    echo "📋 Последние строки лога админ-панели:"
    tail -10 /tmp/logs/admin.log
    kill $BOT_PID 2>/dev/null
    exit 1
fi

echo "🎉 Все сервисы запущены успешно!"
echo "🤖 Telegram бот: PID $BOT_PID"
echo "🌐 Админ-панель: PID $ADMIN_PID"
echo "🌐 Админ-панель доступна: http://0.0.0.0:8080"
echo "📋 Логи бота: /tmp/logs/bot.log"
echo "📋 Логи админ-панели: /tmp/logs/admin.log"
echo "📊 Мониторинг активен..."

# Запускаем мониторинг в фоне
monitor_process $BOT_PID "Telegram бот" &
monitor_process $ADMIN_PID "Админ-панель" &

# Основной цикл мониторинга
while true; do
    # Проверяем статус бота
    if ! kill -0 $BOT_PID 2>/dev/null; then
        echo "❌ Бот завершился!"
        echo "📋 Последние строки лога бота:"
        tail -10 /tmp/logs/bot.log
        break
    fi
    
    # Проверяем статус админ-панели
    if ! kill -0 $ADMIN_PID 2>/dev/null; then
        echo "❌ Админ-панель завершилась!"
        echo "📋 Последние строки лога админ-панели:"
        tail -10 /tmp/logs/admin.log
        break
    fi
    
    # Выводим статус каждые 60 секунд
    sleep 60
    echo "✅ $(date): Все сервисы работают (Bot: $BOT_PID, Admin: $ADMIN_PID)"
done

# Если дошли сюда, один из процессов завершился
cleanup

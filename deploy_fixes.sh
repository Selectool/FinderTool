#!/bin/bash

# Скрипт для развертывания исправлений на production сервер
# Исправляет проблемы с админ-панелью и базой данных

echo "🚀 РАЗВЕРТЫВАНИЕ ИСПРАВЛЕНИЙ НА PRODUCTION СЕРВЕР"
echo "=================================================="

# Проверяем, что мы в правильной директории
if [ ! -f "main.py" ]; then
    echo "❌ Ошибка: Запустите скрипт из корневой директории проекта"
    exit 1
fi

echo "📁 Текущая директория: $(pwd)"

# Добавляем все изменения в git
echo "📝 Добавляем изменения в git..."
git add .

# Коммитим изменения
echo "💾 Создаем коммит..."
git commit -m "🔧 Fix production issues: database columns, payment cleanup, admin panel navigation

- Fix ProductionDatabaseManager SQL queries for PostgreSQL
- Add missing database columns (is_subscribed, unlimited_access, etc.)
- Fix payment cleanup service to work with PostgreSQL
- Update admin panel navigation URLs
- Add production database column fix script"

# Пушим изменения
echo "🌐 Отправляем изменения на GitHub..."
git push origin main

echo "✅ Изменения успешно отправлены на GitHub!"
echo ""
echo "🔧 СЛЕДУЮЩИЕ ШАГИ НА СЕРВЕРЕ:"
echo "1. Подключитесь к серверу: ssh root@185.207.66.201"
echo "2. Перейдите в директорию: cd /app"
echo "3. Обновите код: git pull"
echo "4. Исправьте колонки БД: python fix_production_columns.py"
echo "5. Перезапустите админ-панель: Ctrl+C, затем python run_admin.py"
echo "6. Перезапустите бота: Ctrl+C, затем python main.py"
echo ""
echo "🎯 ОЖИДАЕМЫЕ РЕЗУЛЬТАТЫ:"
echo "- ✅ Страница рассылок будет работать без ошибок"
echo "- ✅ Страница пользователей будет показывать данные"
echo "- ✅ Payment cleanup будет работать с PostgreSQL"
echo "- ✅ Навигация будет корректно работать"
echo "- ✅ Telegram бот будет работать без ошибок is_subscribed"

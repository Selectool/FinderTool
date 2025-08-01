# Telegram Channel Finder Bot - Production Dockerfile
FROM python:3.11-slim

# Создание рабочей директории
WORKDIR /app

# Копирование файлов зависимостей
COPY requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Копирование всего кода проекта
COPY . .

# Создание директорий для логов и данных
RUN mkdir -p /app/logs /app/backups /app/uploads

# Создание скрипта запуска
RUN echo '#!/bin/bash' > /app/start.sh && \
    echo 'set -e' >> /app/start.sh && \
    echo '' >> /app/start.sh && \
    echo 'echo "🚀 Запуск Telegram Channel Finder Bot..."' >> /app/start.sh && \
    echo '' >> /app/start.sh && \
    echo '# Запуск бота в фоне' >> /app/start.sh && \
    echo 'echo "📱 Запуск Telegram бота..."' >> /app/start.sh && \
    echo 'python main.py &' >> /app/start.sh && \
    echo 'BOT_PID=$!' >> /app/start.sh && \
    echo 'echo "✅ Telegram бот запущен (PID: $BOT_PID)"' >> /app/start.sh && \
    echo '' >> /app/start.sh && \
    echo '# Небольшая задержка' >> /app/start.sh && \
    echo 'sleep 3' >> /app/start.sh && \
    echo '' >> /app/start.sh && \
    echo '# Запуск админ-панели' >> /app/start.sh && \
    echo 'echo "🌐 Запуск админ-панели..."' >> /app/start.sh && \
    echo 'python run_admin.py &' >> /app/start.sh && \
    echo 'ADMIN_PID=$!' >> /app/start.sh && \
    echo 'echo "✅ Админ-панель запущена (PID: $ADMIN_PID)"' >> /app/start.sh && \
    echo '' >> /app/start.sh && \
    echo 'echo "🎉 Все сервисы запущены успешно!"' >> /app/start.sh && \
    echo 'echo "📱 Telegram бот: PID $BOT_PID"' >> /app/start.sh && \
    echo 'echo "🌐 Админ-панель: http://localhost:8080 (PID $ADMIN_PID)"' >> /app/start.sh && \
    echo '' >> /app/start.sh && \
    echo '# Функция для корректного завершения' >> /app/start.sh && \
    echo 'cleanup() {' >> /app/start.sh && \
    echo '    echo "🛑 Получен сигнал завершения..."' >> /app/start.sh && \
    echo '    echo "⏹️ Остановка Telegram бота (PID: $BOT_PID)..."' >> /app/start.sh && \
    echo '    kill $BOT_PID 2>/dev/null || true' >> /app/start.sh && \
    echo '    echo "⏹️ Остановка админ-панели (PID: $ADMIN_PID)..."' >> /app/start.sh && \
    echo '    kill $ADMIN_PID 2>/dev/null || true' >> /app/start.sh && \
    echo '    echo "✅ Все процессы остановлены"' >> /app/start.sh && \
    echo '    exit 0' >> /app/start.sh && \
    echo '}' >> /app/start.sh && \
    echo '' >> /app/start.sh && \
    echo '# Обработка сигналов' >> /app/start.sh && \
    echo 'trap cleanup SIGTERM SIGINT' >> /app/start.sh && \
    echo '' >> /app/start.sh && \
    echo '# Ожидание завершения процессов' >> /app/start.sh && \
    echo 'wait' >> /app/start.sh && \
    chmod +x /app/start.sh

# Открытие порта для админ-панели
EXPOSE 8080

# Установка переменных окружения для production
ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=production

# Запуск скрипта
CMD ["/app/start.sh"]

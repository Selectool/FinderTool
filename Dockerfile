# Production-Ready Multi-Stage Dockerfile для Railpack/Dokploy
# Оптимизирован для production деплоя с персистентной PostgreSQL

# Build stage
FROM python:3.11-slim as builder

# Устанавливаем build зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Создаем виртуальное окружение
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Копируем и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.11-slim

# Метаданные для Railpack
LABEL maintainer="InfoBlog360"
LABEL description="Telegram Channel Finder Bot - Production Ready"
LABEL version="2.0.0"
LABEL org.opencontainers.image.source="https://github.com/InfoBlog360/telegram-channel-finder-bot"

# Устанавливаем runtime зависимости
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Копируем виртуальное окружение из builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Создаем пользователя для безопасности
RUN groupadd -r app && useradd -r -g app app

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем исходный код
COPY --chown=app:app . .

# Создаем необходимые директории
RUN mkdir -p logs database/backups uploads && \
    chown -R app:app /app

# Переключаемся на непривилегированного пользователя
USER app

# Переменные окружения для production
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV ENVIRONMENT=production
ENV ADMIN_HOST=0.0.0.0
ENV ADMIN_PORT=8000

# Health check для Railpack/Dokploy
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${ADMIN_PORT}/health || exit 1

# Expose порт
EXPOSE 8000

# Команда запуска для Dokploy (можно переопределить в Run Command)
CMD ["python", "dokploy_launcher.py"]

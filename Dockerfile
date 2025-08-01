# Dockerfile для Telegram Channel Finder Bot
FROM python:3.11-slim

# Создание рабочей директории
WORKDIR /app

# Копирование файла зависимостей
COPY requirements-docker.txt requirements.txt

# Установка Python зависимостей
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --only-binary=all -r requirements.txt

# Копирование кода приложения
COPY . .

# Создание необходимых директорий
RUN mkdir -p logs backups uploads

# Установка переменных окружения
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV ENVIRONMENT=production
ENV DATABASE_PATH=bot.db
ENV LOG_LEVEL=INFO

# Команда запуска
CMD ["python", "main.py"]

# Railway Deployment Guide
## Telegram Channel Finder Bot

### Обзор
Этот проект настроен для деплоя на Railway с использованием Railpack buildpack. Все конфигурационные файлы Docker, Nixpacks и Paketo Buildpacks были удалены для чистого деплоя.

### Конфигурационные файлы

#### Основные файлы для Railway/Railpack:
- `Procfile` - определяет команду запуска приложения
- `runtime.txt` - указывает версию Python (3.11)
- `.python-version` - альтернативный способ указания версии Python
- `railpack.json` - дополнительные настройки для Railpack
- `requirements.txt` - зависимости Python (оптимизированы для продакшн)
- `.env.example` - шаблон переменных окружения

### Процесс деплоя

#### 1. Подготовка проекта
```bash
# Убедитесь, что все зависимости актуальны
pip install -r requirements.txt

# Проверьте работоспособность локально
python main.py
```

#### 2. Настройка Railway
1. Создайте аккаунт на [Railway](https://railway.app)
2. Подключите GitHub репозиторий
3. Railway автоматически определит Python проект и использует Railpack

#### 3. Переменные окружения
Настройте следующие переменные в Railway Dashboard:

**Обязательные:**
- `BOT_TOKEN` - токен Telegram бота
- `API_ID` - Telegram API ID
- `API_HASH` - Telegram API Hash
- `ADMIN_USER_ID` - ID администратора
- `YOOKASSA_SHOP_ID` - ID магазина ЮKassa
- `YOOKASSA_SECRET_KEY` - секретный ключ ЮKassa
- `ADMIN_SECRET_KEY` - секретный ключ админ-панели

**Дополнительные:**
- `ENVIRONMENT=production`
- `LOG_LEVEL=INFO`
- `SUBSCRIPTION_PRICE=500`
- `FREE_REQUESTS_LIMIT=3`

#### 4. Домен и webhook
1. В Railway Dashboard настройте кастомный домен или используйте предоставленный
2. Обновите переменную `WEBHOOK_DOMAIN` с вашим доменом
3. Настройте webhook в ЮKassa на `https://your-domain.railway.app/webhook`

### Особенности Railpack

#### Автоматическое определение:
- Railpack автоматически определяет Python проект по наличию `main.py`
- Использует `requirements.txt` для установки зависимостей
- Применяет настройки из `Procfile` для команды запуска

#### Переменные окружения времени выполнения:
```
PYTHONFAULTHANDLER=1
PYTHONUNBUFFERED=1
PYTHONHASHSEED=random
PYTHONDONTWRITEBYTECODE=1
PIP_DISABLE_PIP_VERSION_CHECK=1
PIP_DEFAULT_TIMEOUT=100
```

#### Системные зависимости:
Railpack автоматически устанавливает системные зависимости для:
- PostgreSQL (libpq-dev, libpq5)
- PDF обработки (poppler-utils для pdf2image)
- Аудио обработки (ffmpeg для pydub)

### Мониторинг и логи

#### Просмотр логов:
```bash
# Установите Railway CLI
npm install -g @railway/cli

# Войдите в аккаунт
railway login

# Подключитесь к проекту
railway link

# Просмотр логов в реальном времени
railway logs
```

#### Health check:
Приложение должно отвечать на health check запросы. Убедитесь, что ваш бот корректно обрабатывает webhook запросы.

### Troubleshooting

#### Проблемы с запуском:
1. Проверьте логи через Railway Dashboard или CLI
2. Убедитесь, что все переменные окружения настроены
3. Проверьте корректность `Procfile`

#### Проблемы с базой данных:
1. SQLite файлы сохраняются в эфемерном хранилище
2. Для постоянного хранения рассмотрите использование Railway PostgreSQL
3. Настройте регулярные бэкапы через админ-панель

#### Проблемы с платежами:
1. Убедитесь, что webhook URL корректно настроен в ЮKassa
2. Проверьте переменные `YOOKASSA_*` в Railway
3. Используйте тестовый режим для отладки

### Масштабирование

Railway автоматически масштабирует приложение на основе нагрузки. Для дополнительной настройки:

1. Используйте Railway Pro план для больших нагрузок
2. Настройте мониторинг через встроенные метрики
3. Рассмотрите использование Redis для кэширования

### Безопасность

1. Все секретные ключи храните только в переменных окружения Railway
2. Используйте HTTPS для всех webhook URL
3. Регулярно обновляйте зависимости
4. Мониторьте логи на предмет подозрительной активности

### Поддержка

- [Railway Documentation](https://docs.railway.app)
- [Railpack Documentation](https://railpack.com)
- [Railway Community](https://discord.gg/railway)

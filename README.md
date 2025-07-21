# Telegram Channel Finder Bot

Бот для поиска похожих каналов в Telegram с системой монетизации.

## Функционал

- 🔍 Поиск похожих каналов по ссылкам
- 💰 Система лимитов: 3 бесплатных запроса, затем подписка 500₽/месяц
- 👨‍💼 Админ-панель для рассылок
- 📊 База данных пользователей и статистика

## Установка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/InfoBlog360/telegram-channel-finder-bot.git
cd telegram-channel-finder-bot
```

2. Создайте виртуальное окружение:
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# или
.venv\Scripts\activate  # Windows
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

4. Настройте переменные окружения:
```bash
cp .env.example .env
# Отредактируйте .env файл с вашими данными
```

5. Получите API ключи:
   - Telegram Bot Token: [@BotFather](https://t.me/BotFather)
   - API_ID и API_HASH: [my.telegram.org](https://my.telegram.org)

## Запуск

```bash
python main.py
```

## Структура проекта

```
telegram-channel-finder-bot/
├── main.py                 # Точка входа
├── bot/
│   ├── __init__.py
│   ├── handlers/           # Обработчики команд
│   ├── middlewares/        # Middleware
│   ├── keyboards/          # Клавиатуры
│   └── utils/              # Утилиты
├── database/
│   ├── __init__.py
│   ├── models.py           # Модели БД
│   └── database.py         # Подключение к БД
├── services/
│   ├── __init__.py
│   ├── channel_finder.py   # Поиск каналов
│   └── payment.py          # Платежи
└── config.py               # Конфигурация
```

## Лицензия

MIT License

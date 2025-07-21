# Инструкция по настройке Telegram Channel Finder Bot

## 🚀 Быстрый старт

### 1. Получение API ключей

#### Telegram API (обязательно)
1. Перейдите на [my.telegram.org](https://my.telegram.org)
2. Войдите с помощью вашего номера телефона
3. Перейдите в "API development tools"
4. Создайте новое приложение:
   - App title: `Channel Finder Bot`
   - Short name: `channel_finder`
   - Platform: `Desktop`
5. Скопируйте `API_ID` и `API_HASH`

#### Admin User ID
1. Напишите боту [@userinfobot](https://t.me/userinfobot)
2. Скопируйте ваш User ID

### 2. Настройка конфигурации

Отредактируйте файл `.env`:

```env
# Telegram Bot API Token (уже настроен)
BOT_TOKEN=8066350716:AAHEDXC0kL_L-TXui8vxI0HhD0wchIzl1hI

# Telegram API credentials (ОБЯЗАТЕЛЬНО ЗАПОЛНИТЬ!)
API_ID=ваш_api_id
API_HASH=ваш_api_hash

# Admin settings (ОБЯЗАТЕЛЬНО ЗАПОЛНИТЬ!)
ADMIN_USER_ID=ваш_telegram_user_id

# Остальные настройки можно оставить по умолчанию
DATABASE_URL=sqlite:///bot.db
SUBSCRIPTION_PRICE=500
FREE_REQUESTS_LIMIT=3
SESSION_NAME=bot_session
```

### 3. Запуск бота

```bash
# Активируйте виртуальное окружение
.venv\Scripts\activate  # Windows
# или
source .venv/bin/activate  # Linux/Mac

# Запустите бота
python main.py
```

### 4. Первый запуск

При первом запуске Telethon попросит:
1. Ввести номер телефона
2. Ввести код подтверждения из Telegram
3. Возможно, пароль двухфакторной аутентификации

Это нужно для создания сессии для работы с Telegram API.

## 📋 Проверка работы

1. Найдите бота: [@TgChannelFinderBot](https://t.me/TgChannelFinderBot)
2. Отправьте `/start`
3. Отправьте ссылку на канал, например: `https://t.me/durov`
4. Получите список похожих каналов

## 🛠 Возможные проблемы

### Ошибка "API_ID не установлен"
- Убедитесь, что в `.env` файле указаны корректные `API_ID` и `API_HASH`
- Проверьте, что значения не содержат лишних пробелов

### Ошибка "Phone number required"
- При первом запуске введите ваш номер телефона в международном формате
- Пример: `+79123456789`

### Ошибка "No similar channels found"
- Не все каналы имеют похожие каналы в базе Telegram
- Попробуйте другие популярные каналы

### Бот не отвечает
- Проверьте, что бот запущен (`python main.py`)
- Проверьте логи в консоли на наличие ошибок

## 📊 Админ функции

Для администратора доступны команды:
- `/admin` - Админ панель
- Статистика пользователей
- Рассылка сообщений

## 🔧 Разработка

### Структура проекта
```
telegram-channel-finder-bot/
├── main.py                 # Точка входа
├── config.py              # Конфигурация
├── bot/                   # Логика бота
│   ├── handlers/          # Обработчики команд
│   ├── keyboards/         # Клавиатуры
│   └── middlewares/       # Middleware
├── database/              # База данных
├── services/              # Бизнес-логика
└── requirements.txt       # Зависимости
```

### Добавление новых функций
1. Создайте новый обработчик в `bot/handlers/`
2. Подключите роутер в `main.py`
3. При необходимости обновите модели БД в `database/models.py`

## 📝 Логи

Логи выводятся в консоль. Для продакшена рекомендуется настроить запись в файл:

```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
```

## 🚀 Деплой

Для деплоя на сервер:
1. Установите зависимости: `pip install -r requirements.txt`
2. Настройте `.env` файл
3. Запустите через systemd или supervisor
4. Настройте nginx для проксирования (если нужно)

## 📞 Поддержка

При возникновении проблем:
1. Проверьте логи в консоли
2. Убедитесь в корректности настроек в `.env`
3. Проверьте подключение к интернету
4. Обратитесь к разработчику

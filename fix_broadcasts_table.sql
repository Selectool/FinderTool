-- Исправление таблицы broadcasts для устранения ошибки NOT NULL constraint
-- Выполнить в PostgreSQL: psql postgresql://findertool_user:Findertool1999!@postgres:5432/findertool_prod

-- 1. Проверяем текущую структуру таблицы broadcasts
\d broadcasts;

-- 2. Делаем колонку message nullable (разрешаем NULL значения)
ALTER TABLE broadcasts ALTER COLUMN message DROP NOT NULL;

-- 3. Проверяем, что изменение применилось
\d broadcasts;

-- 4. Обновляем существующие записи с NULL значениями
UPDATE broadcasts 
SET message = COALESCE(message_text, title, 'Сообщение не указано')
WHERE message IS NULL;

-- 5. Проверяем результат
SELECT id, title, message, message_text 
FROM broadcasts 
WHERE message IS NULL OR message = '';

-- 6. Альтернативно: можно установить значение по умолчанию
ALTER TABLE broadcasts ALTER COLUMN message SET DEFAULT '';

-- 7. Проверяем финальную структуру
\d broadcasts;

-- Готово! Теперь создание рассылок должно работать без ошибок.

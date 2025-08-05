#!/usr/bin/env python3
"""
Быстрое исправление для production сервера
"""
import asyncio
import asyncpg
import os

async def quick_fix():
    """Быстрое исправление таблицы broadcasts"""
    
    # Подключение к базе данных
    DATABASE_URL = "postgresql://findertool_user:Findertool1999!@postgres:5432/findertool_prod"
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        print("✅ Подключение к БД установлено")
        
        # 1. Делаем колонку message nullable
        try:
            await conn.execute("ALTER TABLE broadcasts ALTER COLUMN message DROP NOT NULL")
            print("✅ Колонка message теперь nullable")
        except Exception as e:
            print(f"⚠️ Колонка уже nullable или ошибка: {e}")
        
        # 2. Устанавливаем значение по умолчанию
        try:
            await conn.execute("ALTER TABLE broadcasts ALTER COLUMN message SET DEFAULT ''")
            print("✅ Установлено значение по умолчанию")
        except Exception as e:
            print(f"⚠️ Ошибка установки значения по умолчанию: {e}")
        
        # 3. Обновляем существующие записи
        try:
            result = await conn.execute("""
                UPDATE broadcasts 
                SET message = COALESCE(message_text, title, 'Сообщение не указано')
                WHERE message IS NULL
            """)
            print(f"✅ Обновлены записи: {result}")
        except Exception as e:
            print(f"⚠️ Ошибка обновления записей: {e}")
        
        print("🎉 Исправление завершено!")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        try:
            await conn.close()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(quick_fix())

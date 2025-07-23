import asyncio
import aiosqlite

async def check_tables():
    async with aiosqlite.connect('bot.db') as db:
        cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = await cursor.fetchall()
        print('Таблицы в БД:')
        for table in tables:
            print(f'- {table[0]}')
        
        # Проверим админ пользователя
        cursor = await db.execute("SELECT username, role FROM admin_users")
        admin_users = await cursor.fetchall()
        print('\nАдмин пользователи:')
        for user in admin_users:
            print(f'- {user[0]} ({user[1]})')

if __name__ == "__main__":
    asyncio.run(check_tables())

import sqlite3
import os

print("🔍 АНАЛИЗ БАЗ ДАННЫХ")
print("=" * 50)

# Проверяем bot.db
if os.path.exists('bot.db'):
    print("\n📁 bot.db:")
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"Таблицы: {tables}")
    
    if 'users' in tables:
        cursor.execute('SELECT COUNT(*) FROM users')
        count = cursor.fetchone()[0]
        print(f"Пользователей: {count}")
        
        if count > 0:
            cursor.execute('SELECT user_id, username, first_name FROM users LIMIT 3')
            users = cursor.fetchall()
            for user in users:
                print(f"  - ID: {user[0]}, @{user[1]}, {user[2]}")
    
    conn.close()
else:
    print("❌ bot.db не найден")

# Проверяем bot_dev.db
if os.path.exists('bot_dev.db'):
    print("\n📁 bot_dev.db:")
    conn = sqlite3.connect('bot_dev.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"Таблицы: {tables}")
    
    if 'users' in tables:
        cursor.execute('SELECT COUNT(*) FROM users')
        count = cursor.fetchone()[0]
        print(f"Пользователей: {count}")
    
    conn.close()
else:
    print("❌ bot_dev.db не найден")

print("\n💡 РЕКОМЕНДАЦИИ:")
print("1. Использовать единую базу данных для всех компонентов")
print("2. Настроить правильные пути в конфигурации")
print("3. Создать систему миграций для production-ready уровня")

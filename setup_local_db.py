#!/usr/bin/env python3
"""
Скрипт для настройки локальной PostgreSQL базы данных
"""
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sys
import getpass

def create_local_database():
    """Создание локальной базы данных"""
    
    # Возможные пароли для postgres
    possible_passwords = ['password', 'postgres', '123456', 'admin', '']
    
    print("🔧 Настройка локальной PostgreSQL базы данных...")
    print("📋 Пробуем подключиться к PostgreSQL...")
    
    connection = None
    password = None
    
    # Пробуем стандартные пароли
    for pwd in possible_passwords:
        try:
            print(f"🔑 Пробуем пароль: {'(пустой)' if pwd == '' else pwd}")
            connection = psycopg2.connect(
                host='localhost',
                port='5432',
                user='postgres',
                password=pwd,
                database='postgres'
            )
            password = pwd
            print(f"✅ Подключение успешно с паролем: {'(пустой)' if pwd == '' else pwd}")
            break
        except psycopg2.OperationalError as e:
            print(f"❌ Не удалось подключиться с паролем '{pwd}': {e}")
            continue
    
    # Если стандартные пароли не подошли, запрашиваем у пользователя
    if connection is None:
        print("\n🔐 Стандартные пароли не подошли. Введите пароль для пользователя postgres:")
        while connection is None:
            password = getpass.getpass("Пароль postgres: ")
            try:
                connection = psycopg2.connect(
                    host='localhost',
                    port='5432',
                    user='postgres',
                    password=password,
                    database='postgres'
                )
                print("✅ Подключение успешно!")
                break
            except psycopg2.OperationalError as e:
                print(f"❌ Неверный пароль: {e}")
                retry = input("Попробовать еще раз? (y/n): ")
                if retry.lower() != 'y':
                    print("❌ Отмена настройки базы данных")
                    return False
    
    try:
        # Устанавливаем автокоммит для создания базы данных
        connection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = connection.cursor()
        
        # Проверяем, существует ли база данных
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = 'telegram_bot_local'")
        exists = cursor.fetchone()
        
        if exists:
            print("📋 База данных 'telegram_bot_local' уже существует")
            
            # Спрашиваем, нужно ли пересоздать
            recreate = input("🔄 Пересоздать базу данных? (y/n): ")
            if recreate.lower() == 'y':
                print("🗑️ Удаляем существующую базу данных...")
                cursor.execute("DROP DATABASE telegram_bot_local")
                print("✅ База данных удалена")
                
                print("🏗️ Создаем новую базу данных...")
                cursor.execute("CREATE DATABASE telegram_bot_local")
                print("✅ База данных 'telegram_bot_local' создана")
            else:
                print("📋 Используем существующую базу данных")
        else:
            print("🏗️ Создаем базу данных 'telegram_bot_local'...")
            cursor.execute("CREATE DATABASE telegram_bot_local")
            print("✅ База данных 'telegram_bot_local' создана")
        
        cursor.close()
        connection.close()
        
        # Обновляем .env файл
        print("📝 Обновляем .env файл...")
        update_env_file(password)
        
        print("\n🎉 Настройка локальной базы данных завершена!")
        print(f"📊 Строка подключения: postgresql://postgres:{password}@localhost:5432/telegram_bot_local")
        print("🚀 Теперь можно запускать бота!")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при создании базы данных: {e}")
        return False
    finally:
        if connection:
            connection.close()

def update_env_file(password):
    """Обновление .env файла с правильной строкой подключения"""
    try:
        with open('.env', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Заменяем строку DATABASE_URL
        new_db_url = f"DATABASE_URL=postgresql://postgres:{password}@localhost:5432/telegram_bot_local"
        
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if line.startswith('DATABASE_URL='):
                lines[i] = new_db_url
                break
        
        with open('.env', 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        print("✅ .env файл обновлен")
        
    except Exception as e:
        print(f"⚠️ Не удалось обновить .env файл: {e}")
        print(f"📝 Пожалуйста, обновите DATABASE_URL вручную:")
        print(f"   DATABASE_URL=postgresql://postgres:{password}@localhost:5432/telegram_bot_local")

def test_connection():
    """Тестирование подключения к базе данных"""
    try:
        from dotenv import load_dotenv
        import os
        
        load_dotenv()
        database_url = os.getenv('DATABASE_URL')
        
        print(f"🔍 Тестируем подключение: {database_url}")
        
        connection = psycopg2.connect(database_url)
        cursor = connection.cursor()
        cursor.execute("SELECT version()")
        version = cursor.fetchone()
        
        print(f"✅ Подключение успешно! PostgreSQL версия: {version[0]}")
        
        cursor.close()
        connection.close()
        return True
        
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Настройка локальной PostgreSQL базы данных для Telegram Channel Finder Bot")
    print("=" * 70)
    
    if create_local_database():
        print("\n🧪 Тестируем подключение...")
        test_connection()
    else:
        print("❌ Настройка не завершена")
        sys.exit(1)

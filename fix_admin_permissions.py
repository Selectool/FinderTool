#!/usr/bin/env python3
"""
Скрипт для исправления прав доступа в админ-панели
"""

import asyncio
import os
import sys
from datetime import datetime

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.universal_database import UniversalDatabase
from admin.auth.auth import get_password_hash


async def fix_admin_permissions():
    """Исправить права доступа для админ-панели"""
    try:
        print("🔧 Исправление прав доступа в админ-панели...")
        
        # Инициализируем базу данных
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            print("❌ DATABASE_URL не найден в переменных окружения")
            return False
            
        db = UniversalDatabase(database_url)
        
        # Проверяем подключение
        await db.adapter.connect()
        print("✅ Подключение к базе данных установлено")
        
        # Обновляем роль пользователя infoblog_developer
        try:
            # Сначала проверяем, существует ли пользователь
            check_query = """
                SELECT id, username, role FROM admin_users 
                WHERE username = $1
            """
            user = await db.adapter.fetch_one(check_query, ('infoblog_developer',))
            
            if user:
                print(f"📋 Найден пользователь: {user['username']}, текущая роль: {user['role']}")
                
                # Обновляем роль на developer
                update_query = """
                    UPDATE admin_users 
                    SET role = $1, updated_at = $2
                    WHERE username = $3
                """
                await db.adapter.execute(update_query, ('developer', datetime.now(), 'infoblog_developer'))
                print("✅ Роль пользователя обновлена на 'developer'")
                
            else:
                print("⚠️ Пользователь infoblog_developer не найден, создаем...")
                
                # Создаем пользователя с правами developer
                password_hash = get_password_hash("admin123")
                create_query = """
                    INSERT INTO admin_users (username, email, password_hash, role, is_active, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """
                await db.adapter.execute(create_query, (
                    'infoblog_developer',
                    'infoblog@developer.com',
                    password_hash,
                    'developer',
                    True,
                    datetime.now(),
                    datetime.now()
                ))
                print("✅ Пользователь infoblog_developer создан с ролью 'developer'")
        
        except Exception as e:
            print(f"❌ Ошибка при работе с пользователем: {e}")
            return False
        
        # Проверяем права доступа
        print("\n🔍 Проверка прав доступа...")
        from admin.auth.auth import get_user_permissions, check_permission
        
        permissions = get_user_permissions('developer')
        print(f"📋 Права роли 'developer': {permissions}")
        
        # Проверяем конкретные права
        required_permissions = [
            'users.view', 'users.edit', 'users.manage_subscription',
            'statistics.view', 'broadcasts.create', 'broadcasts.send'
        ]
        
        for perm in required_permissions:
            has_perm = check_permission('developer', perm)
            status = "✅" if has_perm else "❌"
            print(f"{status} {perm}: {'Есть' if has_perm else 'Нет'}")
        
        # Проверяем таблицы базы данных
        print("\n🗄️ Проверка таблиц базы данных...")
        
        tables_to_check = ['users', 'requests', 'admin_users', 'broadcasts']
        for table in tables_to_check:
            try:
                count_query = f"SELECT COUNT(*) FROM {table}"
                result = await db.adapter.fetch_one(count_query, ())
                count = result['count'] if result else 0
                print(f"✅ Таблица {table}: {count} записей")
            except Exception as e:
                print(f"❌ Ошибка проверки таблицы {table}: {e}")
        
        await db.adapter.disconnect()
        print("\n✅ Исправление прав доступа завершено успешно!")
        return True
        
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        return False


async def test_admin_connection():
    """Тестировать подключение к админ-панели"""
    try:
        print("\n🧪 Тестирование подключения к админ-панели...")
        
        # Тестируем аутентификацию
        from admin.auth.auth import authenticate_user
        
        database_url = os.getenv('DATABASE_URL')
        db = UniversalDatabase(database_url)
        
        # Пытаемся аутентифицировать пользователя
        user = await authenticate_user(db, 'infoblog_developer', 'admin123')
        
        if user:
            print(f"✅ Аутентификация успешна: {user.username}, роль: {user.role}")
            
            # Проверяем права
            from admin.auth.auth import check_permission
            can_view_users = check_permission(user.role, 'users.view')
            can_edit_users = check_permission(user.role, 'users.edit')
            can_manage_subscription = check_permission(user.role, 'users.manage_subscription')
            
            print(f"✅ Права просмотра пользователей: {'Есть' if can_view_users else 'Нет'}")
            print(f"✅ Права редактирования пользователей: {'Есть' if can_edit_users else 'Нет'}")
            print(f"✅ Права управления подписками: {'Есть' if can_manage_subscription else 'Нет'}")
            
        else:
            print("❌ Ошибка аутентификации")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        return False


async def main():
    """Главная функция"""
    print("🚀 ИСПРАВЛЕНИЕ ПРАВ ДОСТУПА АДМИН-ПАНЕЛИ")
    print("=" * 50)
    
    # Исправляем права
    success = await fix_admin_permissions()
    if not success:
        print("❌ Не удалось исправить права доступа")
        return
    
    # Тестируем подключение
    success = await test_admin_connection()
    if not success:
        print("❌ Тестирование не прошло")
        return
    
    print("\n🎉 Все исправления применены успешно!")
    print("💡 Теперь можно перезапустить админ-панель")


if __name__ == "__main__":
    asyncio.run(main())

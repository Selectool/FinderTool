#!/usr/bin/env python3
"""
Тестирование подключения к PostgreSQL через внешний IP VPS
"""

import socket
import subprocess
import os

def test_external_postgres():
    """Тестирование подключения к PostgreSQL через внешний IP"""
    print("🔍 Тестирование подключения к PostgreSQL через внешний IP VPS")
    print("=" * 60)
    
    # IP VPS сервера
    vps_ip = "185.207.66.201"
    
    # Учетные данные
    username = "findertool_user"
    password = "Findertool1999!"
    database = "findertool_prod"
    port = 5432
    
    print(f"🌐 VPS IP: {vps_ip}")
    print(f"👤 Пользователь: {username}")
    print(f"🗄️ База данных: {database}")
    print(f"🔌 Порт: {port}")
    print()
    
    # 1. Проверяем DNS резолюцию IP
    print("1️⃣ Проверка DNS резолюции...")
    try:
        resolved_ip = socket.gethostbyname(vps_ip)
        print(f"✅ DNS: {vps_ip} -> {resolved_ip}")
    except Exception as e:
        print(f"❌ DNS ошибка: {e}")
        return None
    
    # 2. Проверяем доступность порта
    print("\n2️⃣ Проверка доступности порта PostgreSQL...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        result = sock.connect_ex((vps_ip, port))
        sock.close()
        
        if result == 0:
            print(f"✅ Порт {vps_ip}:{port} доступен")
        else:
            print(f"❌ Порт {vps_ip}:{port} недоступен (код: {result})")
            print("⚠️ Возможные причины:")
            print("   - PostgreSQL не запущен")
            print("   - Firewall блокирует порт 5432")
            print("   - PostgreSQL настроен только для localhost")
            return None
    except Exception as e:
        print(f"❌ Ошибка подключения к порту: {e}")
        return None
    
    # 3. Тестируем подключение к PostgreSQL
    print("\n3️⃣ Тестирование подключения к PostgreSQL...")
    external_url = f"postgresql://{username}:{password}@{vps_ip}:{port}/{database}"
    
    try:
        import psycopg2
        print(f"🔗 Подключение: {external_url[:50]}...")
        
        conn = psycopg2.connect(external_url)
        cursor = conn.cursor()
        
        # Проверяем версию PostgreSQL
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"✅ PostgreSQL подключение успешно!")
        print(f"📊 Версия: {version}")
        
        # Проверяем доступные базы данных
        cursor.execute("SELECT datname FROM pg_database WHERE datistemplate = false;")
        databases = cursor.fetchall()
        print(f"🗄️ Доступные базы: {[db[0] for db in databases]}")
        
        # Проверяем таблицы в нашей базе
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()
        if tables:
            print(f"📋 Таблицы в {database}: {[t[0] for t in tables]}")
        else:
            print(f"⚠️ Таблицы в базе {database} не найдены (возможно, нужны миграции)")
        
        cursor.close()
        conn.close()
        
        return external_url
        
    except Exception as e:
        print(f"❌ Ошибка PostgreSQL: {e}")
        print("\n🔧 Возможные решения:")
        print("1. Проверьте, что PostgreSQL запущен на VPS")
        print("2. Убедитесь, что PostgreSQL принимает внешние подключения")
        print("3. Проверьте настройки pg_hba.conf и postgresql.conf")
        print("4. Убедитесь, что firewall не блокирует порт 5432")
        return None

def check_postgresql_config():
    """Проверка конфигурации PostgreSQL на VPS"""
    print("\n4️⃣ Рекомендации по настройке PostgreSQL на VPS...")
    print("-" * 50)
    
    print("Для подключения извне PostgreSQL должен быть настроен:")
    print()
    print("📝 /etc/postgresql/*/main/postgresql.conf:")
    print("   listen_addresses = '*'")
    print("   port = 5432")
    print()
    print("📝 /etc/postgresql/*/main/pg_hba.conf:")
    print("   host    all             all             0.0.0.0/0               md5")
    print()
    print("🔥 Firewall (ufw):")
    print("   sudo ufw allow 5432")
    print()
    print("🔄 Перезапуск PostgreSQL:")
    print("   sudo systemctl restart postgresql")

def generate_correct_database_url(working_url):
    """Генерация правильного DATABASE_URL для Dokploy"""
    if not working_url:
        return
    
    print("\n" + "=" * 60)
    print("🎉 РЕШЕНИЕ НАЙДЕНО!")
    print("=" * 60)
    
    print(f"\n✅ Рабочий DATABASE_URL:")
    print(f"{working_url}")
    
    print(f"\n🔧 Обновите в Dokploy:")
    print("1. Откройте настройки приложения")
    print("2. Найдите DATABASE_URL")
    print("3. Замените на:")
    print(f"   DATABASE_URL={working_url}")
    print("4. Сохраните и перезапустите приложение")
    
    # Создаем файл с правильным URL
    with open('correct_database_url.env', 'w') as f:
        f.write(f"# Правильный DATABASE_URL для внешнего подключения\n")
        f.write(f"# Сгенерировано: {os.popen('date').read().strip()}\n\n")
        f.write(f"DATABASE_URL={working_url}\n")
    
    print(f"\n💾 Создан файл: correct_database_url.env")

def main():
    print("🔗 ТЕСТИРОВАНИЕ ПОДКЛЮЧЕНИЯ К POSTGRESQL ЧЕРЕЗ ВНЕШНИЙ IP")
    print("=" * 70)
    
    # Тестируем подключение через внешний IP
    working_url = test_external_postgres()
    
    # Показываем рекомендации по настройке
    check_postgresql_config()
    
    # Генерируем правильный URL если подключение работает
    generate_correct_database_url(working_url)
    
    if not working_url:
        print("\n" + "=" * 70)
        print("❌ ПОДКЛЮЧЕНИЕ НЕ УДАЛОСЬ")
        print("=" * 70)
        print("\n🔧 СЛЕДУЮЩИЕ ШАГИ:")
        print("1. Подключитесь к VPS: ssh root@185.207.66.201")
        print("2. Проверьте статус PostgreSQL: sudo systemctl status postgresql")
        print("3. Настройте PostgreSQL для внешних подключений (см. выше)")
        print("4. Перезапустите PostgreSQL: sudo systemctl restart postgresql")
        print("5. Повторите тест")

if __name__ == "__main__":
    main()

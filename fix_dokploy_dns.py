#!/usr/bin/env python3
"""
Исправление DNS резолюции для PostgreSQL в Dokploy
Поиск правильного IP для findertool-hyvrte
"""

import socket
import subprocess
import ipaddress
import os
from concurrent.futures import ThreadPoolExecutor

def get_container_info():
    """Получение информации о текущем контейнере"""
    print("🐳 ИНФОРМАЦИЯ О КОНТЕЙНЕРЕ")
    print("=" * 40)
    
    hostname = socket.gethostname()
    container_ip = socket.gethostbyname(hostname)
    
    print(f"📍 Hostname: {hostname}")
    print(f"📍 IP: {container_ip}")
    
    # Определяем сеть
    try:
        network = ipaddress.IPv4Network(f"{container_ip}/24", strict=False)
        print(f"📍 Сеть: {network}")
        return container_ip, network
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return container_ip, None

def scan_postgres_hosts(network):
    """Сканирование сети на PostgreSQL"""
    print(f"\n🔍 ПОИСК POSTGRESQL В СЕТИ {network}")
    print("=" * 50)
    
    postgres_hosts = []
    
    def check_host(ip):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((str(ip), 5432))
            sock.close()
            
            if result == 0:
                return str(ip)
        except:
            pass
        return None
    
    # Сканируем сеть
    print("🔍 Сканирование...")
    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(check_host, ip) for ip in network.hosts()]
        
        for future in futures:
            result = future.result()
            if result:
                postgres_hosts.append(result)
                print(f"✅ PostgreSQL найден на {result}:5432")
    
    return postgres_hosts

def test_postgres_connection(host, expected_name="findertool-hyvrte"):
    """Тестирование подключения к PostgreSQL"""
    print(f"\n🧪 ТЕСТИРОВАНИЕ {host}")
    print("-" * 30)
    
    # Учетные данные из Dokploy
    username = "findertool_user"
    password = "Findertool1999!"
    database = "findertool_prod"
    port = 5432
    
    test_url = f"postgresql://{username}:{password}@{host}:{port}/{database}"
    
    try:
        import psycopg2
        conn = psycopg2.connect(test_url)
        cursor = conn.cursor()
        
        # Проверяем версию
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        
        # Проверяем базы данных
        cursor.execute("SELECT datname FROM pg_database WHERE datistemplate = false;")
        databases = [db[0] for db in cursor.fetchall()]
        
        # Проверяем таблицы
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        tables = [t[0] for t in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        print(f"✅ Подключение успешно!")
        print(f"📊 Версия: {version[:50]}...")
        print(f"🗄️ Базы: {databases}")
        print(f"📋 Таблицы: {tables[:5]}{'...' if len(tables) > 5 else ''}")
        
        return {
            'host': host,
            'url': test_url,
            'version': version,
            'databases': databases,
            'tables': tables
        }
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return None

def create_hosts_file_entry(postgres_ip):
    """Создание записи для /etc/hosts"""
    print(f"\n📝 СОЗДАНИЕ ЗАПИСИ /etc/hosts")
    print("=" * 40)
    
    hosts_entry = f"{postgres_ip}    findertool-hyvrte"
    
    print(f"Добавьте в /etc/hosts:")
    print(f"{hosts_entry}")
    
    # Пытаемся добавить автоматически (может не сработать из-за прав)
    try:
        with open('/etc/hosts', 'a') as f:
            f.write(f"\n# PostgreSQL Dokploy\n{hosts_entry}\n")
        print("✅ Запись добавлена в /etc/hosts")
        return True
    except Exception as e:
        print(f"❌ Не удалось добавить автоматически: {e}")
        
        # Создаем файл с командой
        with open('add_hosts_entry.sh', 'w') as f:
            f.write(f"#!/bin/bash\n")
            f.write(f"# Добавление записи для PostgreSQL\n")
            f.write(f"echo '{hosts_entry}' >> /etc/hosts\n")
        
        print("💾 Создан файл add_hosts_entry.sh")
        print("Выполните: bash add_hosts_entry.sh")
        return False

def test_dns_resolution():
    """Тестирование DNS резолюции после исправления"""
    print(f"\n🔍 ТЕСТИРОВАНИЕ DNS РЕЗОЛЮЦИИ")
    print("=" * 40)
    
    try:
        ip = socket.gethostbyname('findertool-hyvrte')
        print(f"✅ findertool-hyvrte -> {ip}")
        return ip
    except Exception as e:
        print(f"❌ DNS ошибка: {e}")
        return None

def generate_solution(working_connection):
    """Генерация итогового решения"""
    if not working_connection:
        return
    
    print(f"\n🎉 РЕШЕНИЕ НАЙДЕНО!")
    print("=" * 50)
    
    host = working_connection['host']
    url = working_connection['url']
    
    print(f"✅ PostgreSQL найден на IP: {host}")
    print(f"✅ Рабочий DATABASE_URL: {url}")
    
    # Создаем правильный URL с именем хоста
    correct_url = url.replace(f"@{host}:", "@findertool-hyvrte:")
    
    print(f"\n🔧 ПРАВИЛЬНЫЙ DATABASE_URL ДЛЯ DOKPLOY:")
    print(f"{correct_url}")
    
    print(f"\n📋 ШАГИ ДЛЯ ИСПРАВЛЕНИЯ:")
    print("1. Добавьте запись в /etc/hosts контейнера:")
    print(f"   {host}    findertool-hyvrte")
    print("2. Или используйте прямой IP в DATABASE_URL:")
    print(f"   DATABASE_URL={url}")
    print("3. Перезапустите приложение")
    
    # Сохраняем решения
    with open('postgres_solution.env', 'w') as f:
        f.write(f"# Решение проблемы PostgreSQL в Dokploy\n\n")
        f.write(f"# Вариант 1: Прямой IP\n")
        f.write(f"DATABASE_URL={url}\n\n")
        f.write(f"# Вариант 2: С именем хоста (требует /etc/hosts)\n")
        f.write(f"DATABASE_URL={correct_url}\n\n")
        f.write(f"# Запись для /etc/hosts:\n")
        f.write(f"# {host}    findertool-hyvrte\n")
    
    print(f"\n💾 Решения сохранены в postgres_solution.env")

def main():
    print("🔧 ИСПРАВЛЕНИЕ DNS ДЛЯ POSTGRESQL В DOKPLOY")
    print("=" * 60)
    
    # 1. Получаем информацию о контейнере
    container_ip, network = get_container_info()
    
    if not network:
        print("❌ Не удалось определить сеть")
        return
    
    # 2. Ищем PostgreSQL в сети
    postgres_hosts = scan_postgres_hosts(network)
    
    if not postgres_hosts:
        print(f"\n❌ PostgreSQL не найден в сети {network}")
        print("\n💡 АЛЬТЕРНАТИВНЫЕ РЕШЕНИЯ:")
        print("1. PostgreSQL может быть в другой сети")
        print("2. Используйте внешний PostgreSQL")
        print("3. Проверьте статус PostgreSQL сервиса в Dokploy")
        return
    
    # 3. Тестируем найденные PostgreSQL
    working_connections = []
    for host in postgres_hosts:
        result = test_postgres_connection(host)
        if result:
            working_connections.append(result)
    
    if not working_connections:
        print(f"\n❌ PostgreSQL найден, но подключение не удалось")
        print("🔧 Проверьте учетные данные и настройки базы")
        return
    
    # 4. Выбираем лучшее подключение
    best_connection = working_connections[0]
    postgres_ip = best_connection['host']
    
    # 5. Создаем запись для /etc/hosts
    create_hosts_file_entry(postgres_ip)
    
    # 6. Тестируем DNS резолюцию
    resolved_ip = test_dns_resolution()
    
    # 7. Генерируем итоговое решение
    generate_solution(best_connection)
    
    print(f"\n" + "=" * 60)
    print("📊 ИТОГ:")
    if resolved_ip:
        print("✅ DNS резолюция исправлена")
        print("✅ Используйте оригинальный DATABASE_URL из Dokploy")
    else:
        print("⚠️ DNS резолюция не исправлена")
        print("✅ Используйте DATABASE_URL с прямым IP")

if __name__ == "__main__":
    main()

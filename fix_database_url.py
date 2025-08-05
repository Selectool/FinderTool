#!/usr/bin/env python3
"""
Quick Fix для DATABASE_URL в Dokploy
Автоматическое исправление подключения к PostgreSQL
"""

import os
import sys
import socket
import subprocess
from urllib.parse import urlparse

def find_working_postgres_host():
    """Поиск рабочего PostgreSQL хоста"""
    print("🔍 Поиск рабочего PostgreSQL хоста...")
    
    # Возможные имена хостов в Dokploy (в порядке приоритета)
    possible_hosts = [
        'findertool-db',  # НАИБОЛЕЕ ВЕРОЯТНЫЙ - видно в Dokploy UI
        'postgres',
        'postgresql',
        'db',
        'database',
        'localhost',
        '127.0.0.1',
        'postgres-inGABWIP0OB6grXZXTORS',  # По ID сервиса
        'findertool-postgres'
    ]
    
    # Учетные данные из переменных окружения
    username = 'findertool_user'
    password = 'Findertool1999!'
    database = 'findertool_prod'
    port = 5432
    
    working_hosts = []
    
    for host in possible_hosts:
        try:
            print(f"  🧪 Тестирование {host}...")
            
            # Проверяем DNS
            try:
                ip = socket.gethostbyname(host)
                print(f"    ✅ DNS: {host} -> {ip}")
            except socket.gaierror:
                print(f"    ❌ DNS: {host} не резолвится")
                continue
            
            # Проверяем порт
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result != 0:
                print(f"    ❌ Порт: {host}:{port} недоступен")
                continue
            
            print(f"    ✅ Порт: {host}:{port} доступен")
            
            # Проверяем PostgreSQL
            test_url = f"postgresql://{username}:{password}@{host}:{port}/{database}"
            try:
                import psycopg2
                conn = psycopg2.connect(test_url)
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.close()
                conn.close()
                print(f"    ✅ PostgreSQL: подключение успешно")
                working_hosts.append((host, test_url))
            except Exception as e:
                print(f"    ❌ PostgreSQL: {e}")
                
        except Exception as e:
            print(f"    ❌ Общая ошибка: {e}")
    
    return working_hosts

def show_current_config():
    """Показать текущую конфигурацию"""
    print("📊 ТЕКУЩАЯ КОНФИГУРАЦИЯ:")
    print("-" * 30)
    
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        try:
            parsed = urlparse(database_url)
            print(f"Схема: {parsed.scheme}")
            print(f"Хост: {parsed.hostname}")
            print(f"Порт: {parsed.port}")
            print(f"База: {parsed.path[1:] if parsed.path else 'не указана'}")
            print(f"Пользователь: {parsed.username}")
            print(f"Полный URL: {database_url[:50]}...")
        except Exception as e:
            print(f"❌ Ошибка парсинга: {e}")
    else:
        print("❌ DATABASE_URL не установлен")
    
    print()

def show_docker_info():
    """Показать информацию о Docker окружении"""
    print("🐳 ИНФОРМАЦИЯ О DOCKER ОКРУЖЕНИИ:")
    print("-" * 40)
    
    try:
        # Показываем hostname
        hostname = socket.gethostname()
        print(f"Hostname: {hostname}")
        
        # Показываем /etc/hosts
        try:
            with open('/etc/hosts', 'r') as f:
                hosts = f.read()
                print("\n/etc/hosts:")
                for line in hosts.split('\n'):
                    if line.strip() and not line.startswith('#'):
                        print(f"  {line}")
        except:
            print("  ⚠️ Не удалось прочитать /etc/hosts")
        
        # Показываем сетевые интерфейсы
        try:
            result = subprocess.run(['ip', 'addr', 'show'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print("\nСетевые интерфейсы:")
                for line in result.stdout.split('\n'):
                    if 'inet ' in line and ('172.' in line or '192.' in line or '10.' in line):
                        print(f"  {line.strip()}")
        except:
            print("  ⚠️ Не удалось получить сетевые интерфейсы")
            
    except Exception as e:
        print(f"❌ Ошибка получения Docker информации: {e}")
    
    print()

def generate_dokploy_commands(working_hosts):
    """Генерация команд для обновления в Dokploy"""
    if not working_hosts:
        print("❌ Нет рабочих хостов для генерации команд")
        return
    
    print("🔧 КОМАНДЫ ДЛЯ ОБНОВЛЕНИЯ В DOKPLOY:")
    print("-" * 40)
    
    best_host, best_url = working_hosts[0]
    
    print(f"1. Откройте Dokploy админ-панель")
    print(f"2. Перейдите в настройки приложения (Environment)")
    print(f"3. Измените DATABASE_URL на:")
    print(f"   {best_url}")
    print(f"4. Сохраните изменения и перезапустите приложение")
    print()
    
    print("Альтернативно, если у вас есть доступ к CLI:")
    print(f"export DATABASE_URL='{best_url}'")
    print()

def create_fixed_env_file(working_hosts):
    """Создание файла с исправленными переменными окружения"""
    if not working_hosts:
        return
    
    best_host, best_url = working_hosts[0]
    
    env_content = f"""# Исправленные переменные окружения для Dokploy
# Сгенерировано автоматически: {os.popen('date').read().strip()}

# ИСПРАВЛЕННОЕ ПОДКЛЮЧЕНИЕ К БД
DATABASE_URL={best_url}

# Остальные переменные остаются без изменений
ENVIRONMENT=production
DATABASE_TYPE=postgresql
SERVICE_TYPE=unified

# Скопируйте DATABASE_URL выше в настройки Dokploy
"""
    
    with open('fixed_database_url.env', 'w') as f:
        f.write(env_content)
    
    print(f"💾 Создан файл fixed_database_url.env с исправленным DATABASE_URL")
    print(f"📋 Скопируйте DATABASE_URL из этого файла в настройки Dokploy")

def main():
    print("🔧 АВТОМАТИЧЕСКОЕ ИСПРАВЛЕНИЕ DATABASE_URL")
    print("=" * 50)
    print()
    
    # Показываем текущую конфигурацию
    show_current_config()
    
    # Показываем Docker информацию
    show_docker_info()
    
    # Ищем рабочие хосты
    working_hosts = find_working_postgres_host()
    
    print("\n" + "=" * 50)
    print("📊 РЕЗУЛЬТАТЫ:")
    
    if working_hosts:
        print(f"✅ Найдено {len(working_hosts)} рабочих подключений:")
        for i, (host, url) in enumerate(working_hosts, 1):
            print(f"  {i}. {host}: {url}")
        
        print()
        generate_dokploy_commands(working_hosts)
        create_fixed_env_file(working_hosts)
        
        print("🎉 ГОТОВО! Используйте исправленный DATABASE_URL в Dokploy")
        
    else:
        print("❌ НЕ НАЙДЕНО РАБОЧИХ ПОДКЛЮЧЕНИЙ")
        print()
        print("🔧 ВОЗМОЖНЫЕ РЕШЕНИЯ:")
        print("1. Убедитесь, что PostgreSQL сервис запущен в Dokploy")
        print("2. Проверьте, что сервисы находятся в одной Docker сети")
        print("3. Проверьте учетные данные PostgreSQL")
        print("4. Обратитесь к документации Dokploy по настройке сети")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Поиск PostgreSQL в Docker сети Dokploy
Сканирование внутренней сети для поиска PostgreSQL
"""

import socket
import subprocess
import ipaddress
import threading
from concurrent.futures import ThreadPoolExecutor

def get_container_network_info():
    """Получение информации о сети контейнера"""
    print("🐳 ИНФОРМАЦИЯ О DOCKER СЕТИ")
    print("=" * 40)
    
    # Получаем IP контейнера
    hostname = socket.gethostname()
    container_ip = socket.gethostbyname(hostname)
    
    print(f"📍 Hostname контейнера: {hostname}")
    print(f"📍 IP контейнера: {container_ip}")
    
    # Определяем сеть
    try:
        network = ipaddress.IPv4Network(f"{container_ip}/24", strict=False)
        print(f"📍 Предполагаемая сеть: {network}")
        return network
    except Exception as e:
        print(f"❌ Ошибка определения сети: {e}")
        return None

def scan_port(ip, port, timeout=2):
    """Сканирование порта на IP"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((str(ip), port))
        sock.close()
        return result == 0
    except:
        return False

def scan_postgres_in_network(network):
    """Сканирование сети на наличие PostgreSQL"""
    print(f"\n🔍 СКАНИРОВАНИЕ СЕТИ {network} НА POSTGRESQL")
    print("=" * 50)
    
    postgres_hosts = []
    
    def check_ip(ip):
        ip_str = str(ip)
        if scan_port(ip_str, 5432, timeout=1):
            print(f"✅ Найден PostgreSQL на {ip_str}:5432")
            return ip_str
        return None
    
    # Сканируем сеть параллельно
    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = []
        for ip in network.hosts():
            futures.append(executor.submit(check_ip, ip))
        
        for future in futures:
            result = future.result()
            if result:
                postgres_hosts.append(result)
    
    return postgres_hosts

def test_postgres_connection(host):
    """Тестирование подключения к PostgreSQL"""
    print(f"\n🧪 ТЕСТИРОВАНИЕ POSTGRESQL НА {host}")
    print("-" * 40)
    
    # Учетные данные
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
        print(f"✅ Подключение успешно!")
        print(f"📊 Версия: {version}")
        
        # Проверяем базы данных
        cursor.execute("SELECT datname FROM pg_database WHERE datistemplate = false;")
        databases = cursor.fetchall()
        print(f"🗄️ Базы данных: {[db[0] for db in databases]}")
        
        cursor.close()
        conn.close()
        
        return test_url
        
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        return None

def check_docker_compose_networks():
    """Проверка Docker Compose сетей"""
    print(f"\n🌐 DOCKER COMPOSE СЕТИ")
    print("=" * 30)
    
    try:
        # Получаем список сетей
        result = subprocess.run(['docker', 'network', 'ls'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("📋 Доступные Docker сети:")
            for line in result.stdout.split('\n')[1:]:
                if line.strip():
                    print(f"  {line}")
        
        # Пытаемся получить информацию о текущей сети
        result = subprocess.run(['docker', 'network', 'inspect', 'bridge'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"\n📊 Информация о bridge сети получена")
        
    except Exception as e:
        print(f"❌ Ошибка получения информации о сетях: {e}")

def generate_working_database_url(working_hosts):
    """Генерация рабочего DATABASE_URL"""
    if not working_hosts:
        return
    
    print(f"\n🎉 НАЙДЕНЫ РАБОЧИЕ POSTGRESQL ХОСТЫ!")
    print("=" * 50)
    
    for i, (host, url) in enumerate(working_hosts, 1):
        print(f"\n{i}. Хост: {host}")
        print(f"   URL: {url}")
    
    # Выбираем лучший вариант
    best_host, best_url = working_hosts[0]
    
    print(f"\n✅ РЕКОМЕНДУЕМЫЙ DATABASE_URL:")
    print(f"{best_url}")
    
    print(f"\n🔧 ОБНОВИТЕ В DOKPLOY:")
    print("1. Откройте настройки приложения")
    print("2. Найдите DATABASE_URL")
    print("3. Замените на:")
    print(f"   DATABASE_URL={best_url}")
    print("4. Сохраните и перезапустите")
    
    # Сохраняем в файл
    with open('working_database_url.env', 'w') as f:
        f.write(f"# Рабочий DATABASE_URL найден автоматически\n")
        f.write(f"# Хост: {best_host}\n")
        f.write(f"DATABASE_URL={best_url}\n")
    
    print(f"\n💾 Сохранено в файл: working_database_url.env")

def main():
    print("🔍 ПОИСК POSTGRESQL В DOCKER СЕТИ DOKPLOY")
    print("=" * 60)
    
    # 1. Получаем информацию о сети
    network = get_container_network_info()
    
    if not network:
        print("❌ Не удалось определить сеть контейнера")
        return
    
    # 2. Проверяем Docker сети
    check_docker_compose_networks()
    
    # 3. Сканируем сеть на PostgreSQL
    postgres_ips = scan_postgres_in_network(network)
    
    if not postgres_ips:
        print(f"\n❌ PostgreSQL не найден в сети {network}")
        print("\n🔧 ВОЗМОЖНЫЕ ПРИЧИНЫ:")
        print("1. PostgreSQL запущен в другой Docker сети")
        print("2. PostgreSQL использует нестандартный порт")
        print("3. PostgreSQL запущен на внешнем сервере")
        print("4. Firewall блокирует сканирование")
        
        print(f"\n💡 АЛЬТЕРНАТИВНЫЕ РЕШЕНИЯ:")
        print("1. Запустите: python diagnose_vps_postgres.py")
        print("2. Проверьте PostgreSQL сервис в Dokploy")
        print("3. Используйте внешний PostgreSQL сервер")
        return
    
    # 4. Тестируем найденные PostgreSQL хосты
    working_hosts = []
    for ip in postgres_ips:
        working_url = test_postgres_connection(ip)
        if working_url:
            working_hosts.append((ip, working_url))
    
    # 5. Генерируем рабочий DATABASE_URL
    generate_working_database_url(working_hosts)
    
    if not working_hosts:
        print(f"\n❌ Найдены PostgreSQL серверы, но подключение не удалось")
        print("🔧 Возможные проблемы:")
        print("1. Неправильные учетные данные")
        print("2. База данных не создана")
        print("3. Неправильные права доступа")
        print("4. PostgreSQL настроен только для localhost")

if __name__ == "__main__":
    main()

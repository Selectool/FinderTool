#!/usr/bin/env python3
"""
Диагностика PostgreSQL на VPS 185.207.66.201
Генерация команд для настройки PostgreSQL
"""

import socket
import subprocess
import os

def check_vps_connectivity():
    """Проверка базовой связности с VPS"""
    vps_ip = "185.207.66.201"
    
    print("🌐 ПРОВЕРКА СВЯЗНОСТИ С VPS")
    print("=" * 40)
    
    # Ping тест
    print(f"📡 Ping тест {vps_ip}...")
    try:
        result = subprocess.run(['ping', '-c', '3', vps_ip], 
                              capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            print("✅ VPS доступен по ping")
        else:
            print("❌ VPS недоступен по ping")
            return False
    except Exception as e:
        print(f"❌ Ошибка ping: {e}")
        return False
    
    # SSH порт тест
    print(f"\n🔐 Проверка SSH порта (22)...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((vps_ip, 22))
        sock.close()
        
        if result == 0:
            print("✅ SSH порт (22) доступен")
        else:
            print("❌ SSH порт (22) недоступен")
            return False
    except Exception as e:
        print(f"❌ Ошибка SSH теста: {e}")
        return False
    
    return True

def check_postgres_port():
    """Проверка порта PostgreSQL"""
    vps_ip = "185.207.66.201"
    
    print(f"\n🗄️ ПРОВЕРКА POSTGRESQL ПОРТА")
    print("=" * 40)
    
    # Стандартный порт PostgreSQL
    print(f"🔌 Проверка порта 5432...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        result = sock.connect_ex((vps_ip, 5432))
        sock.close()
        
        if result == 0:
            print("✅ PostgreSQL порт (5432) доступен")
            return True
        else:
            print("❌ PostgreSQL порт (5432) недоступен")
            print(f"   Код ошибки: {result}")
            return False
    except Exception as e:
        print(f"❌ Ошибка проверки порта: {e}")
        return False

def generate_vps_setup_commands():
    """Генерация команд для настройки PostgreSQL на VPS"""
    print(f"\n🔧 КОМАНДЫ ДЛЯ НАСТРОЙКИ POSTGRESQL НА VPS")
    print("=" * 50)
    
    commands = [
        "# 1. Подключение к VPS",
        "ssh root@185.207.66.201",
        "",
        "# 2. Проверка статуса PostgreSQL",
        "sudo systemctl status postgresql",
        "sudo systemctl status postgresql@*",
        "",
        "# 3. Если PostgreSQL не установлен:",
        "sudo apt update",
        "sudo apt install postgresql postgresql-contrib -y",
        "",
        "# 4. Запуск PostgreSQL",
        "sudo systemctl start postgresql",
        "sudo systemctl enable postgresql",
        "",
        "# 5. Создание пользователя и базы данных",
        "sudo -u postgres psql",
        "CREATE USER findertool_user WITH PASSWORD 'Findertool1999!';",
        "CREATE DATABASE findertool_prod OWNER findertool_user;",
        "GRANT ALL PRIVILEGES ON DATABASE findertool_prod TO findertool_user;",
        "\\q",
        "",
        "# 6. Настройка для внешних подключений",
        "# Редактируем postgresql.conf",
        "sudo nano /etc/postgresql/*/main/postgresql.conf",
        "# Найдите и измените:",
        "# listen_addresses = '*'",
        "# port = 5432",
        "",
        "# 7. Настройка аутентификации",
        "# Редактируем pg_hba.conf",
        "sudo nano /etc/postgresql/*/main/pg_hba.conf",
        "# Добавьте в конец файла:",
        "# host    all             all             0.0.0.0/0               md5",
        "",
        "# 8. Настройка firewall",
        "sudo ufw status",
        "sudo ufw allow 5432/tcp",
        "sudo ufw reload",
        "",
        "# 9. Перезапуск PostgreSQL",
        "sudo systemctl restart postgresql",
        "",
        "# 10. Проверка подключения",
        "sudo -u postgres psql -h localhost -p 5432 -U findertool_user -d findertool_prod",
        "",
        "# 11. Проверка портов",
        "sudo netstat -tlnp | grep 5432",
        "sudo ss -tlnp | grep 5432"
    ]
    
    for cmd in commands:
        print(cmd)
    
    # Сохраняем команды в файл
    with open('vps_postgres_setup.sh', 'w') as f:
        f.write("#!/bin/bash\n")
        f.write("# Команды для настройки PostgreSQL на VPS 185.207.66.201\n\n")
        for cmd in commands:
            if not cmd.startswith('#') and cmd.strip():
                f.write(f"{cmd}\n")
    
    print(f"\n💾 Команды сохранены в файл: vps_postgres_setup.sh")

def generate_quick_test_commands():
    """Генерация команд для быстрой проверки"""
    print(f"\n⚡ БЫСТРАЯ ДИАГНОСТИКА НА VPS")
    print("=" * 40)
    
    quick_commands = [
        "# Подключитесь к VPS и выполните:",
        "ssh root@185.207.66.201",
        "",
        "# Быстрая проверка PostgreSQL:",
        "sudo systemctl is-active postgresql",
        "sudo systemctl is-enabled postgresql",
        "sudo netstat -tlnp | grep 5432",
        "sudo ufw status | grep 5432",
        "",
        "# Проверка конфигурации:",
        "sudo -u postgres psql -c \"SHOW listen_addresses;\"",
        "sudo -u postgres psql -c \"SHOW port;\"",
        "",
        "# Проверка пользователей и баз:",
        "sudo -u postgres psql -c \"\\du\"",
        "sudo -u postgres psql -c \"\\l\"",
    ]
    
    for cmd in quick_commands:
        print(cmd)

def check_dokploy_postgres():
    """Проверка PostgreSQL в Dokploy"""
    print(f"\n🐳 ПРОВЕРКА POSTGRESQL В DOKPLOY")
    print("=" * 40)
    
    print("1. Откройте Dokploy PostgreSQL сервис:")
    print("   https://app.dokploy.com/dashboard/project/11aoVJ3mH1tcOu4BiGxVB/services/postgres/inGABWIP0OB6grXZXTORS")
    print()
    print("2. Проверьте статус сервиса (должен быть 'Running')")
    print()
    print("3. Проверьте логи PostgreSQL сервиса")
    print()
    print("4. Убедитесь, что переменные окружения правильные:")
    print("   POSTGRES_DB=findertool_prod")
    print("   POSTGRES_USER=findertool_user")
    print("   POSTGRES_PASSWORD=Findertool1999!")
    print()
    print("5. Если сервис не запущен - перезапустите его")

def main():
    print("🔍 ДИАГНОСТИКА POSTGRESQL НА VPS 185.207.66.201")
    print("=" * 60)
    
    # 1. Проверяем базовую связность
    if not check_vps_connectivity():
        print("\n❌ VPS недоступен. Проверьте сетевое подключение.")
        return
    
    # 2. Проверяем порт PostgreSQL
    postgres_available = check_postgres_port()
    
    # 3. Генерируем команды для настройки
    generate_vps_setup_commands()
    
    # 4. Быстрая диагностика
    generate_quick_test_commands()
    
    # 5. Проверка Dokploy
    check_dokploy_postgres()
    
    # 6. Итоговые рекомендации
    print(f"\n" + "=" * 60)
    print("📊 ИТОГОВЫЕ РЕКОМЕНДАЦИИ:")
    print("=" * 60)
    
    if postgres_available:
        print("✅ PostgreSQL порт доступен - попробуйте подключение")
        print("   python test_external_db.py")
    else:
        print("❌ PostgreSQL порт недоступен")
        print("\n🔧 СЛЕДУЮЩИЕ ШАГИ:")
        print("1. Подключитесь к VPS: ssh root@185.207.66.201")
        print("2. Выполните быструю диагностику (команды выше)")
        print("3. Настройте PostgreSQL (используйте vps_postgres_setup.sh)")
        print("4. Или используйте PostgreSQL из Dokploy с правильным именем хоста")
        
        print("\n💡 АЛЬТЕРНАТИВНОЕ РЕШЕНИЕ:")
        print("Если PostgreSQL запущен в Dokploy, найдите правильное имя хоста:")
        print("- Проверьте логи Dokploy PostgreSQL сервиса")
        print("- Попробуйте подключиться из приложения к внутреннему IP")
        print("- Используйте Docker network inspect для поиска IP PostgreSQL")

if __name__ == "__main__":
    main()

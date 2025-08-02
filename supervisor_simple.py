#!/usr/bin/env python3
"""
Простой Python скрипт для запуска с Supervisor без установки пакетов
"""
import subprocess
import sys
import os
import time
import signal
from pathlib import Path

# Устанавливаем переменные окружения
os.environ["ENVIRONMENT"] = "production"
os.environ["PYTHONPATH"] = "/app"
os.environ["PYTHONUNBUFFERED"] = "1"

class SupervisorManager:
    def __init__(self):
        self.supervisor_config = """
[supervisord]
nodaemon=true
user=root
logfile=/tmp/supervisord.log
pidfile=/tmp/supervisord.pid
childlogdir=/tmp
loglevel=info

[unix_http_server]
file=/tmp/supervisor.sock
chmod=0700

[supervisorctl]
serverurl=unix:///tmp/supervisor.sock

[rpcinterface:supervisor]
supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface

[program:telegram_bot]
command=python main.py
directory=/app
autostart=true
autorestart=true
startretries=3
user=root
redirect_stderr=true
stdout_logfile=/tmp/telegram_bot.log
stdout_logfile_maxbytes=50MB
stdout_logfile_backups=5
environment=ENVIRONMENT=production,PYTHONPATH=/app,PYTHONUNBUFFERED=1

[program:admin_panel]
command=python run_admin.py
directory=/app
autostart=true
autorestart=true
startretries=3
user=root
redirect_stderr=true
stdout_logfile=/tmp/admin_panel.log
stdout_logfile_maxbytes=50MB
stdout_logfile_backups=5
environment=ENVIRONMENT=production,PYTHONPATH=/app,PYTHONUNBUFFERED=1
priority=999

[group:findertool_services]
programs=telegram_bot,admin_panel
priority=999
"""
        self.supervisor_process = None
        
    def install_supervisor(self):
        """Установка supervisor если не установлен"""
        try:
            subprocess.run(["supervisord", "--version"], 
                         check=True, capture_output=True)
            print("✅ Supervisor уже установлен")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("📦 Установка Supervisor...")
            try:
                subprocess.run([
                    "apt-get", "update", "&&", 
                    "apt-get", "install", "-y", "supervisor"
                ], shell=True, check=True)
                print("✅ Supervisor установлен")
                return True
            except subprocess.CalledProcessError:
                print("❌ Ошибка установки Supervisor")
                return False
    
    def create_config(self):
        """Создание конфигурации supervisor"""
        config_path = "/tmp/supervisord.conf"
        try:
            with open(config_path, 'w') as f:
                f.write(self.supervisor_config)
            print(f"✅ Конфигурация создана: {config_path}")
            return config_path
        except Exception as e:
            print(f"❌ Ошибка создания конфигурации: {e}")
            return None
    
    def start_supervisor(self, config_path):
        """Запуск supervisor"""
        try:
            print("🔄 Запуск Supervisor...")
            self.supervisor_process = subprocess.Popen([
                "supervisord", "-c", config_path
            ])
            
            # Ждем запуска
            time.sleep(5)
            
            # Проверяем статус
            result = subprocess.run([
                "supervisorctl", "-c", config_path, "status"
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ Supervisor запущен успешно")
                print("📊 Статус сервисов:")
                print(result.stdout)
                return True
            else:
                print("❌ Ошибка запуска Supervisor")
                print(result.stderr)
                return False
                
        except Exception as e:
            print(f"❌ Ошибка запуска Supervisor: {e}")
            return False
    
    def monitor_services(self, config_path):
        """Мониторинг сервисов"""
        print("📊 Мониторинг сервисов...")
        print("🌐 Админ-панель: http://0.0.0.0:8080")
        print("📋 Логи бота: tail -f /tmp/telegram_bot.log")
        print("📋 Логи админ-панели: tail -f /tmp/admin_panel.log")
        print("🔧 Для остановки используйте Ctrl+C")
        
        try:
            while True:
                time.sleep(30)
                
                # Проверяем статус
                result = subprocess.run([
                    "supervisorctl", "-c", config_path, "status"
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    bot_status = "UNKNOWN"
                    admin_status = "UNKNOWN"
                    
                    for line in lines:
                        if "telegram_bot" in line:
                            bot_status = line.split()[1]
                        elif "admin_panel" in line:
                            admin_status = line.split()[1]
                    
                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                    print(f"{timestamp} - Bot: {bot_status}, Admin: {admin_status}")
                    
                    # Если оба сервиса не работают
                    if bot_status != "RUNNING" and admin_status != "RUNNING":
                        print("❌ Все сервисы остановлены")
                        break
                else:
                    print("⚠️ Ошибка получения статуса")
                    
        except KeyboardInterrupt:
            print("\n🛑 Получен сигнал остановки...")
            self.stop_supervisor(config_path)
    
    def stop_supervisor(self, config_path):
        """Остановка supervisor"""
        try:
            print("🛑 Остановка сервисов...")
            subprocess.run([
                "supervisorctl", "-c", config_path, "stop", "all"
            ], check=True)
            
            if self.supervisor_process:
                self.supervisor_process.terminate()
                self.supervisor_process.wait(timeout=10)
            
            print("✅ Все сервисы остановлены")
        except Exception as e:
            print(f"⚠️ Ошибка остановки: {e}")
    
    def run(self):
        """Основной метод запуска"""
        print("🚀 Запуск Telegram Channel Finder Bot с Supervisor...")
        
        # Устанавливаем supervisor
        if not self.install_supervisor():
            return False
        
        # Создаем конфигурацию
        config_path = self.create_config()
        if not config_path:
            return False
        
        # Запускаем supervisor
        if not self.start_supervisor(config_path):
            return False
        
        # Мониторим сервисы
        self.monitor_services(config_path)
        
        return True

if __name__ == "__main__":
    manager = SupervisorManager()
    
    def signal_handler(signum, frame):
        print(f"\n🛑 Получен сигнал {signum}")
        manager.stop_supervisor("/tmp/supervisord.conf")
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        success = manager.run()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        sys.exit(1)

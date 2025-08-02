#!/usr/bin/env python3
"""
Быстрый запуск с Supervisor - исправленная версия без pkill
"""
import subprocess
import sys
import os
import time
import signal
import psutil

# Устанавливаем переменные окружения
os.environ["ENVIRONMENT"] = "production"
os.environ["PYTHONPATH"] = "/app"
os.environ["PYTHONUNBUFFERED"] = "1"

class QuickSupervisorFixed:
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
startretries=5
startsecs=10
user=root
redirect_stderr=true
stdout_logfile=/tmp/telegram_bot.log
stdout_logfile_maxbytes=100MB
stdout_logfile_backups=3
environment=ENVIRONMENT=production,PYTHONPATH=/app,PYTHONUNBUFFERED=1
priority=100

[program:admin_panel]
command=python run_admin.py
directory=/app
autostart=true
autorestart=true
startretries=5
startsecs=10
user=root
redirect_stderr=true
stdout_logfile=/tmp/admin_panel.log
stdout_logfile_maxbytes=100MB
stdout_logfile_backups=3
environment=ENVIRONMENT=production,ADMIN_ALLOWED_HOSTS="185.207.66.201,findertool.dokploy.com,localhost,127.0.0.1,0.0.0.0",ADMIN_CORS_ORIGINS="http://185.207.66.201:8080,https://findertool.dokploy.com,http://localhost:8080,http://127.0.0.1:8080",ADMIN_HOST=0.0.0.0,ADMIN_PORT=8080,PYTHONPATH=/app,PYTHONUNBUFFERED=1
priority=200

[group:findertool_services]
programs=telegram_bot,admin_panel
priority=999
"""
        self.config_path = "/tmp/supervisord.conf"
        self.supervisor_process = None
        
    def install_dependencies(self):
        """Установка необходимых зависимостей"""
        try:
            print("📦 Установка необходимых пакетов...")
            
            # Проверяем, есть ли supervisor
            try:
                result = subprocess.run(["supervisord", "--version"], 
                                      capture_output=True, text=True)
                print(f"✅ Supervisor уже установлен: {result.stdout.strip()}")
            except FileNotFoundError:
                print("📥 Установка Supervisor...")
                subprocess.run(["apt-get", "update", "-qq"], check=True)
                subprocess.run(["apt-get", "install", "-y", "supervisor"], check=True)
                print("✅ Supervisor установлен")
            
            # Устанавливаем procps для команд ps, pkill и т.д.
            try:
                subprocess.run(["pkill", "--version"], capture_output=True, check=True)
                print("✅ procps уже установлен")
            except (FileNotFoundError, subprocess.CalledProcessError):
                print("📥 Установка procps...")
                subprocess.run(["apt-get", "install", "-y", "procps"], check=True)
                print("✅ procps установлен")
            
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Ошибка установки зависимостей: {e}")
            return False
    
    def kill_processes_by_name(self, process_names):
        """Остановка процессов по имени с использованием psutil"""
        killed_count = 0
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                for process_name in process_names:
                    if process_name in cmdline:
                        print(f"🔪 Останавливаем процесс: {proc.info['pid']} - {cmdline[:50]}...")
                        proc.terminate()
                        killed_count += 1
                        break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        if killed_count > 0:
            print(f"⏳ Ожидание завершения {killed_count} процессов...")
            time.sleep(3)
            
            # Принудительно убиваем оставшиеся процессы
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    for process_name in process_names:
                        if process_name in cmdline:
                            print(f"💀 Принудительно убиваем: {proc.info['pid']}")
                            proc.kill()
                            break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
    
    def create_config(self):
        """Создание конфигурации supervisor"""
        try:
            with open(self.config_path, 'w') as f:
                f.write(self.supervisor_config)
            print(f"✅ Конфигурация создана: {self.config_path}")
            return True
        except Exception as e:
            print(f"❌ Ошибка создания конфигурации: {e}")
            return False
    
    def start_supervisor(self):
        """Запуск supervisor"""
        try:
            print("🔄 Запуск Supervisor...")
            
            # Останавливаем существующие процессы
            print("🛑 Остановка существующих процессов...")
            self.kill_processes_by_name([
                "supervisord",
                "python main.py",
                "python run_admin.py",
                "python bypass_admin.py"
            ])
            
            # Запускаем supervisor
            self.supervisor_process = subprocess.Popen([
                "supervisord", "-c", self.config_path
            ])
            
            # Ждем запуска
            time.sleep(10)
            
            # Проверяем статус
            result = subprocess.run([
                "supervisorctl", "-c", self.config_path, "status"
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ Supervisor запущен успешно")
                print("📊 Статус сервисов:")
                print(result.stdout)
                print("🌐 Админ-панель: http://185.207.66.201:8080")
                print("🔑 Логин: admin / admin123")
                print("📋 Логи:")
                print("  • tail -f /tmp/telegram_bot.log")
                print("  • tail -f /tmp/admin_panel.log")
                return True
            else:
                print("❌ Ошибка запуска Supervisor")
                print(f"Ошибка: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка запуска Supervisor: {e}")
            return False
    
    def monitor_services(self):
        """Мониторинг сервисов"""
        print("📊 Мониторинг сервисов...")
        
        def signal_handler(signum, frame):
            print(f"\n🛑 Получен сигнал {signum}")
            self.stop_supervisor()
            sys.exit(0)
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        try:
            while True:
                time.sleep(60)
                
                # Проверяем статус
                result = subprocess.run([
                    "supervisorctl", "-c", self.config_path, "status"
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    bot_status = "UNKNOWN"
                    admin_status = "UNKNOWN"
                    
                    for line in lines:
                        if "telegram_bot" in line:
                            parts = line.split()
                            if len(parts) >= 2:
                                bot_status = parts[1]
                        elif "admin_panel" in line:
                            parts = line.split()
                            if len(parts) >= 2:
                                admin_status = parts[1]
                    
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
            self.stop_supervisor()
    
    def stop_supervisor(self):
        """Остановка supervisor"""
        try:
            print("🛑 Остановка сервисов...")
            subprocess.run([
                "supervisorctl", "-c", self.config_path, "stop", "all"
            ])
            
            if self.supervisor_process:
                self.supervisor_process.terminate()
                self.supervisor_process.wait(timeout=10)
            
            print("✅ Все сервисы остановлены")
        except Exception as e:
            print(f"⚠️ Ошибка остановки: {e}")
    
    def run(self):
        """Основной метод запуска"""
        print("🚀 Быстрый запуск с Supervisor (исправленная версия)...")
        
        # Устанавливаем зависимости
        if not self.install_dependencies():
            return False
        
        # Создаем конфигурацию
        if not self.create_config():
            return False
        
        # Запускаем supervisor
        if not self.start_supervisor():
            return False
        
        # Мониторим сервисы
        self.monitor_services()
        
        return True

if __name__ == "__main__":
    supervisor = QuickSupervisorFixed()
    try:
        success = supervisor.run()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        sys.exit(1)

#!/usr/bin/env python3
"""
Launcher script for Telegram Channel Finder Bot
Запускает бота и админ-панель одновременно в Paketo Buildpacks
"""

import subprocess
import sys
import time
import signal
import os
from threading import Thread

class ProcessLauncher:
    def __init__(self):
        self.bot_process = None
        self.admin_process = None
        self.running = True
        
    def signal_handler(self, signum, frame):
        """Обработчик сигналов для корректного завершения"""
        print(f"Получен сигнал {signum}, завершаем процессы...")
        self.running = False
        
        if self.bot_process:
            self.bot_process.terminate()
        if self.admin_process:
            self.admin_process.terminate()
            
        sys.exit(0)
    
    def start_bot(self):
        """Запуск Telegram бота"""
        try:
            print("🤖 Запускаем Telegram бота...")
            self.bot_process = subprocess.Popen(
                [sys.executable, "main.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            # Читаем вывод бота
            for line in iter(self.bot_process.stdout.readline, ''):
                if not self.running:
                    break
                print(f"[BOT] {line.strip()}")
                
        except Exception as e:
            print(f"❌ Ошибка запуска бота: {e}")
    
    def start_admin(self):
        """Запуск админ-панели"""
        try:
            print("🌐 Запускаем админ-панель...")
            self.admin_process = subprocess.Popen(
                [sys.executable, "run_admin.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            # Читаем вывод админ-панели
            for line in iter(self.admin_process.stdout.readline, ''):
                if not self.running:
                    break
                print(f"[ADMIN] {line.strip()}")
                
        except Exception as e:
            print(f"❌ Ошибка запуска админ-панели: {e}")
    
    def run(self):
        """Основной метод запуска"""
        # Регистрируем обработчики сигналов
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        
        print("🚀 Запускаем Telegram Channel Finder Bot...")
        print(f"📁 Рабочая директория: {os.getcwd()}")
        
        # Запускаем процессы в отдельных потоках
        bot_thread = Thread(target=self.start_bot, daemon=True)
        admin_thread = Thread(target=self.start_admin, daemon=True)
        
        bot_thread.start()
        admin_thread.start()
        
        print("✅ Оба процесса запущены!")
        
        try:
            # Ждем завершения процессов
            while self.running:
                # Проверяем статус процессов
                if self.bot_process and self.bot_process.poll() is not None:
                    print("❌ Бот завершился неожиданно!")
                    break
                    
                if self.admin_process and self.admin_process.poll() is not None:
                    print("❌ Админ-панель завершилась неожиданно!")
                    break
                    
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("⏹️ Получен сигнал остановки...")
        finally:
            self.signal_handler(signal.SIGTERM, None)

if __name__ == "__main__":
    launcher = ProcessLauncher()
    launcher.run()

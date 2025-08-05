#!/usr/bin/env python3
"""
Environment Check для Telegram Channel Finder Bot
Проверка окружения, зависимостей и конфигурации
"""

import os
import sys
import subprocess
import importlib
from pathlib import Path
from typing import List, Dict, Any

class EnvironmentChecker:
    """Класс для проверки окружения"""
    
    def __init__(self):
        self.results = {
            'python': {'status': 'unknown', 'details': {}},
            'dependencies': {'status': 'unknown', 'details': {}},
            'environment': {'status': 'unknown', 'details': {}},
            'database': {'status': 'unknown', 'details': {}},
            'directories': {'status': 'unknown', 'details': {}},
            'permissions': {'status': 'unknown', 'details': {}}
        }
    
    def check_python_version(self):
        """Проверка версии Python"""
        try:
            version = sys.version_info
            self.results['python']['details']['version'] = f"{version.major}.{version.minor}.{version.micro}"
            
            if version >= (3, 8):
                self.results['python']['status'] = 'ok'
                self.results['python']['details']['message'] = "Версия Python подходит"
            else:
                self.results['python']['status'] = 'error'
                self.results['python']['details']['message'] = "Требуется Python 3.8 или выше"
                
        except Exception as e:
            self.results['python']['status'] = 'error'
            self.results['python']['details']['error'] = str(e)
    
    def check_dependencies(self):
        """Проверка зависимостей"""
        required_packages = [
            'aiogram',
            'psycopg2',
            'fastapi',
            'uvicorn',
            'jinja2',
            'requests',
            'psutil'
        ]
        
        missing = []
        installed = []
        
        for package in required_packages:
            try:
                importlib.import_module(package)
                installed.append(package)
            except ImportError:
                missing.append(package)
        
        self.results['dependencies']['details']['installed'] = installed
        self.results['dependencies']['details']['missing'] = missing
        
        if not missing:
            self.results['dependencies']['status'] = 'ok'
            self.results['dependencies']['details']['message'] = "Все зависимости установлены"
        else:
            self.results['dependencies']['status'] = 'error'
            self.results['dependencies']['details']['message'] = f"Отсутствуют: {', '.join(missing)}"
    
    def check_environment_variables(self):
        """Проверка переменных окружения"""
        required_vars = {
            'BOT_TOKEN': 'Токен Telegram бота',
            'DATABASE_URL': 'URL подключения к базе данных'
        }
        
        optional_vars = {
            'ENVIRONMENT': 'Окружение (production/development)',
            'ADMIN_PASSWORD': 'Пароль админ-панели',
            'SECRET_KEY': 'Секретный ключ для сессий'
        }
        
        missing_required = []
        present_vars = {}
        
        # Проверяем обязательные
        for var, description in required_vars.items():
            value = os.getenv(var)
            if value:
                # Маскируем чувствительные данные
                if 'TOKEN' in var or 'PASSWORD' in var:
                    present_vars[var] = f"{value[:10]}...{value[-5:]}" if len(value) > 15 else "***"
                else:
                    present_vars[var] = value[:50] + "..." if len(value) > 50 else value
            else:
                missing_required.append(f"{var} ({description})")
        
        # Проверяем опциональные
        for var, description in optional_vars.items():
            value = os.getenv(var)
            if value:
                if 'PASSWORD' in var or 'SECRET' in var:
                    present_vars[var] = "***"
                else:
                    present_vars[var] = value
        
        self.results['environment']['details']['present'] = present_vars
        self.results['environment']['details']['missing_required'] = missing_required
        
        if not missing_required:
            self.results['environment']['status'] = 'ok'
            self.results['environment']['details']['message'] = "Все переменные окружения установлены"
        else:
            self.results['environment']['status'] = 'error'
            self.results['environment']['details']['message'] = f"Отсутствуют: {', '.join(missing_required)}"
    
    def check_database_connection(self):
        """Проверка подключения к базе данных"""
        try:
            database_url = os.getenv('DATABASE_URL')
            if not database_url:
                self.results['database']['status'] = 'error'
                self.results['database']['details']['message'] = "DATABASE_URL не установлен"
                return
            
            import psycopg2
            conn = psycopg2.connect(database_url)
            cursor = conn.cursor()
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            
            self.results['database']['status'] = 'ok'
            self.results['database']['details']['message'] = "Подключение к БД успешно"
            self.results['database']['details']['version'] = version
            
        except Exception as e:
            self.results['database']['status'] = 'error'
            self.results['database']['details']['message'] = f"Ошибка подключения: {e}"
    
    def check_directories(self):
        """Проверка необходимых директорий"""
        required_dirs = [
            'logs',
            'data',
            'database/backups',
            'uploads/broadcasts',
            'temp'
        ]
        
        missing_dirs = []
        existing_dirs = []
        
        for dir_path in required_dirs:
            path = Path(dir_path)
            if path.exists():
                existing_dirs.append(dir_path)
            else:
                missing_dirs.append(dir_path)
        
        self.results['directories']['details']['existing'] = existing_dirs
        self.results['directories']['details']['missing'] = missing_dirs
        
        if not missing_dirs:
            self.results['directories']['status'] = 'ok'
            self.results['directories']['details']['message'] = "Все директории существуют"
        else:
            self.results['directories']['status'] = 'warning'
            self.results['directories']['details']['message'] = f"Отсутствуют: {', '.join(missing_dirs)}"
    
    def check_file_permissions(self):
        """Проверка прав доступа к файлам"""
        critical_files = [
            'unified_startup.py',
            'run_admin.py',
            'config.py'
        ]
        
        permission_issues = []
        accessible_files = []
        
        for file_path in critical_files:
            path = Path(file_path)
            if path.exists():
                if os.access(path, os.R_OK):
                    accessible_files.append(file_path)
                else:
                    permission_issues.append(f"{file_path} (нет прав на чтение)")
            else:
                permission_issues.append(f"{file_path} (файл не существует)")
        
        # Проверяем права на запись в директории логов
        logs_dir = Path('logs')
        if logs_dir.exists() and not os.access(logs_dir, os.W_OK):
            permission_issues.append("logs/ (нет прав на запись)")
        
        self.results['permissions']['details']['accessible'] = accessible_files
        self.results['permissions']['details']['issues'] = permission_issues
        
        if not permission_issues:
            self.results['permissions']['status'] = 'ok'
            self.results['permissions']['details']['message'] = "Права доступа в порядке"
        else:
            self.results['permissions']['status'] = 'error'
            self.results['permissions']['details']['message'] = f"Проблемы: {', '.join(permission_issues)}"
    
    def run_all_checks(self):
        """Запуск всех проверок"""
        print("🔍 Проверка окружения Telegram Channel Finder Bot...")
        print()
        
        checks = [
            ("Python версия", self.check_python_version),
            ("Зависимости", self.check_dependencies),
            ("Переменные окружения", self.check_environment_variables),
            ("База данных", self.check_database_connection),
            ("Директории", self.check_directories),
            ("Права доступа", self.check_file_permissions)
        ]
        
        for name, check_func in checks:
            print(f"🔍 Проверка: {name}...")
            try:
                check_func()
                status = self.results[name.lower().replace(' ', '_').replace('переменные_окружения', 'environment')]['status']
                if status == 'ok':
                    print(f"✅ {name}: OK")
                elif status == 'warning':
                    print(f"⚠️ {name}: Предупреждение")
                else:
                    print(f"❌ {name}: Ошибка")
            except Exception as e:
                print(f"❌ {name}: Исключение - {e}")
            print()
        
        return self.results
    
    def print_detailed_report(self):
        """Печать подробного отчета"""
        print("📊 ПОДРОБНЫЙ ОТЧЕТ:")
        print("=" * 50)
        
        for category, data in self.results.items():
            status_icon = {
                'ok': '✅',
                'warning': '⚠️',
                'error': '❌',
                'unknown': '❓'
            }.get(data['status'], '❓')
            
            print(f"\n{status_icon} {category.upper()}:")
            
            if 'message' in data['details']:
                print(f"  Статус: {data['details']['message']}")
            
            for key, value in data['details'].items():
                if key != 'message':
                    if isinstance(value, list):
                        if value:
                            print(f"  {key}: {', '.join(value)}")
                    else:
                        print(f"  {key}: {value}")

def main():
    checker = EnvironmentChecker()
    results = checker.run_all_checks()
    
    print("\n" + "="*50)
    checker.print_detailed_report()
    
    # Общий статус
    error_count = sum(1 for data in results.values() if data['status'] == 'error')
    warning_count = sum(1 for data in results.values() if data['status'] == 'warning')
    
    print(f"\n📊 ОБЩИЙ СТАТУС:")
    if error_count == 0:
        if warning_count == 0:
            print("✅ Окружение полностью готово к работе!")
        else:
            print(f"⚠️ Окружение готово с {warning_count} предупреждениями")
    else:
        print(f"❌ Обнаружено {error_count} критических ошибок")
        print("Необходимо исправить ошибки перед запуском сервиса")

if __name__ == "__main__":
    main()

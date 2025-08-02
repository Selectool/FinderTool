#!/usr/bin/env python3
"""
Простая рабочая админ-панель
"""
import os
import uvicorn
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Устанавливаем продакшн режим
os.environ["ENVIRONMENT"] = "production"

app = FastAPI(title="Channel Finder Admin Panel")

# HTML шаблоны
LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Channel Finder Admin</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 50px; background: #f5f5f5; }
        .container { max-width: 400px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { text-align: center; color: #333; }
        input { width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
        button { width: 100%; padding: 12px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }
        button:hover { background: #0056b3; }
        .info { background: #e7f3ff; padding: 15px; border-radius: 4px; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 Channel Finder Admin</h1>
        <div class="info">
            <strong>Данные для входа:</strong><br>
            Логин: <code>admin</code><br>
            Пароль: <code>admin123</code>
        </div>
        <form method="post" action="/auth/login">
            <input type="text" name="username" placeholder="Логин" required>
            <input type="password" name="password" placeholder="Пароль" required>
            <button type="submit">Войти</button>
        </form>
    </div>
</body>
</html>
"""

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Admin Dashboard</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 0; background: #f5f5f5; }
        .header { background: #007bff; color: white; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .card { background: white; padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; }
        .stat { text-align: center; }
        .stat h3 { margin: 0; color: #007bff; font-size: 2em; }
        .stat p { margin: 5px 0 0 0; color: #666; }
        .btn { display: inline-block; padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 4px; margin: 5px; }
        .btn:hover { background: #0056b3; }
    </style>
</head>
<body>
    <div class="header">
        <div class="container">
            <h1>🤖 Channel Finder Bot - Админ-панель</h1>
            <p>Добро пожаловать в панель управления</p>
        </div>
    </div>
    <div class="container">
        <div class="card">
            <h2>📊 Статистика</h2>
            <div class="stats">
                <div class="stat">
                    <h3>0</h3>
                    <p>Пользователей</p>
                </div>
                <div class="stat">
                    <h3>0</h3>
                    <p>Запросов</p>
                </div>
                <div class="stat">
                    <h3>0</h3>
                    <p>Платежей</p>
                </div>
                <div class="stat">
                    <h3>✅</h3>
                    <p>Статус бота</p>
                </div>
            </div>
        </div>
        <div class="card">
            <h2>🛠️ Управление</h2>
            <a href="/admin/users" class="btn">👥 Пользователи</a>
            <a href="/admin/broadcasts" class="btn">📢 Рассылки</a>
            <a href="/admin/payments" class="btn">💳 Платежи</a>
            <a href="/admin/settings" class="btn">⚙️ Настройки</a>
        </div>
        <div class="card">
            <h2>ℹ️ Информация о системе</h2>
            <p><strong>Режим:</strong> Production</p>
            <p><strong>База данных:</strong> PostgreSQL</p>
            <p><strong>Статус:</strong> Работает</p>
            <p><strong>Версия:</strong> 1.0.0</p>
        </div>
    </div>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse(url="/auth/login")

@app.get("/auth/login", response_class=HTMLResponse)
async def login_page():
    return LOGIN_HTML

@app.post("/auth/login")
async def login(username: str = Form(...), password: str = Form(...)):
    if username == "admin" and password == "admin123":
        return RedirectResponse(url="/dashboard", status_code=302)
    else:
        raise HTTPException(status_code=401, detail="Неверные данные для входа")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    return DASHBOARD_HTML

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "admin-panel", "database": "postgresql"}

@app.get("/admin/{path:path}")
async def admin_placeholder(path: str):
    return {"message": f"Раздел {path} в разработке", "status": "coming_soon"}

if __name__ == "__main__":
    print("🚀 Запуск простой админ-панели...")
    print("🏠 Адрес: http://0.0.0.0:8080")
    print("👤 Логин: admin / admin123")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        log_level="info"
    )

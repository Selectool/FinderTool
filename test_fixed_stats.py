#!/usr/bin/env python3
"""
Тестирование исправленной статистики рассылок
"""
import asyncio
from database.models import Database

async def test_fixed_stats():
    """Тестировать исправленную статистику"""
    db = Database()
    
    # Тестируем рассылку #3 (последнюю)
    broadcast_id = 3
    
    print(f"=== ТЕСТИРОВАНИЕ СТАТИСТИКИ РАССЫЛКИ #{broadcast_id} ===")
    
    # Получаем основную информацию о рассылке
    broadcast = await db.get_broadcast_by_id(broadcast_id)
    if not broadcast:
        print("Рассылка не найдена!")
        return
    
    print("\nОсновная информация:")
    print(f"ID: {broadcast['id']}")
    print(f"Заголовок: {broadcast['title']}")
    print(f"Статус: {broadcast['status']}")
    print(f"Целевая аудитория: {broadcast['target_users']}")
    print(f"Создано: {broadcast['created_at']}")
    print(f"Запущено: {broadcast['started_at']}")
    print(f"Отправлено (из таблицы): {broadcast['sent_count']}")
    print(f"Ошибок (из таблицы): {broadcast['failed_count']}")
    
    # Получаем детальную статистику
    stats = await db.get_broadcast_detailed_stats(broadcast_id)
    
    print("\nДетальная статистика:")
    print(f"Доставлено: {stats['delivered']}")
    print(f"Ошибок: {stats['failed']}")
    print(f"Заблокировано: {stats['blocked']}")
    print(f"Всего получателей: {stats['total_recipients']}")
    print(f"Скорость отправки: {stats['current_rate']} сообщений/мин")
    print(f"Оставшееся время: {stats['estimated_time']}")
    
    # Рассчитываем успешность правильно
    total_sent = stats['delivered'] + stats['failed'] + stats['blocked']
    if total_sent > 0:
        success_rate = (stats['delivered'] / total_sent) * 100
        print(f"Успешность: {success_rate:.1f}%")
    else:
        print("Успешность: 0.0%")
    
    # Проверяем количество пользователей по типам
    print(f"\n=== ПРОВЕРКА АУДИТОРИЙ ===")
    
    all_count = await db.get_target_audience_count("all")
    active_count = await db.get_target_audience_count("active")
    subscribers_count = await db.get_target_audience_count("subscribers")
    
    print(f"Все пользователи: {all_count}")
    print(f"Активные пользователи: {active_count}")
    print(f"Подписчики: {subscribers_count}")

if __name__ == "__main__":
    asyncio.run(test_fixed_stats())

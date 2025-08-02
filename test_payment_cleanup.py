#!/usr/bin/env python3
"""
Тестирование системы очистки платежей
Проверяет корректность работы исправленной статистики
"""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

from database.models import Database
from services.payment_cleanup import PaymentCleanupService, get_cleanup_service
from services.payment_service import YooKassaPaymentService
from utils.logging_config import setup_logging

logger = setup_logging()

class PaymentCleanupTester:
    """Тестер системы очистки платежей"""
    
    def __init__(self):
        self.db = Database()
        self.cleanup_service = get_cleanup_service(self.db)
        self.payment_service = YooKassaPaymentService(
            provider_token="test_token",
            currency="RUB",
            provider_data={},
            db=self.db
        )
    
    async def setup_test_data(self):
        """Создание тестовых данных"""
        logger.info("🔧 Создание тестовых данных...")
        
        # Создаем тестового пользователя
        test_user_id = 999999999
        await self.db.add_user(
            user_id=test_user_id,
            username="test_user",
            first_name="Test",
            last_name="User"
        )
        
        # Создаем тестовые платежи с разными статусами
        import aiosqlite
        async with aiosqlite.connect(self.db.db_path) as db:
            # 1. Успешный платеж (должен учитываться в статистике)
            await db.execute("""
                INSERT INTO payments (user_id, payment_id, amount, currency, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (test_user_id, "success_payment_1", 34900, "RUB", "completed", datetime.now().isoformat()))
            
            # 2. Ожидающий платеж (новый, не должен отменяться)
            await db.execute("""
                INSERT INTO payments (user_id, payment_id, amount, currency, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (test_user_id, "pending_payment_1", 34900, "RUB", "pending", datetime.now().isoformat()))
            
            # 3. Просроченный платеж (должен отменяться)
            expired_time = datetime.now() - timedelta(hours=1)  # 1 час назад
            await db.execute("""
                INSERT INTO payments (user_id, payment_id, amount, currency, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (test_user_id, "expired_payment_1", 34900, "RUB", "pending", expired_time.isoformat()))
            
            # 4. Еще один просроченный платеж
            expired_time2 = datetime.now() - timedelta(minutes=45)  # 45 минут назад
            await db.execute("""
                INSERT INTO payments (user_id, payment_id, amount, currency, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (test_user_id, "expired_payment_2", 34900, "RUB", "pending", expired_time2.isoformat()))
            
            # 5. Отмененный платеж (не должен учитываться)
            await db.execute("""
                INSERT INTO payments (user_id, payment_id, amount, currency, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (test_user_id, "cancelled_payment_1", 34900, "RUB", "cancelled", datetime.now().isoformat()))
            
            await db.commit()
        
        logger.info("✅ Тестовые данные созданы")
    
    async def test_statistics_before_cleanup(self):
        """Тест статистики до очистки"""
        logger.info("📊 Тестирование статистики ДО очистки...")
        
        stats = await self.payment_service.get_payment_statistics()
        
        logger.info("Статистика ДО очистки:")
        logger.info(f"  - Сегодня: {stats['today']['count']} платежей, {stats['today']['successful']} успешных")
        logger.info(f"  - Всего: {stats['total']['count']} платежей, {stats['total']['successful']} успешных")
        
        # Проверяем, что считается только 1 успешный платеж
        assert stats['today']['successful'] == 1, f"Ожидался 1 успешный платеж, получено {stats['today']['successful']}"
        assert stats['today']['count'] == 1, f"Ожидался 1 платеж в статистике, получено {stats['today']['count']}"
        
        logger.info("✅ Статистика ДО очистки корректна")
        return stats
    
    async def test_cleanup_process(self):
        """Тест процесса очистки"""
        logger.info("🧹 Тестирование процесса очистки...")
        
        # Получаем статистику очистки
        cleanup_stats = await self.cleanup_service.get_cleanup_statistics()
        logger.info(f"Статистика очистки: {cleanup_stats}")
        
        # Выполняем очистку
        cleanup_result = await self.cleanup_service.cleanup_expired_invoices()
        
        logger.info("Результат очистки:")
        logger.info(f"  - Найдено просроченных: {cleanup_result['expired_found']}")
        logger.info(f"  - Отменено: {cleanup_result['cancelled']}")
        logger.info(f"  - Ошибок: {cleanup_result['errors']}")
        
        # Проверяем, что отменено 2 просроченных платежа
        assert cleanup_result['expired_found'] >= 2, f"Ожидалось найти минимум 2 просроченных платежа"
        assert cleanup_result['cancelled'] >= 2, f"Ожидалось отменить минимум 2 платежа"
        
        logger.info("✅ Процесс очистки работает корректно")
        return cleanup_result
    
    async def test_statistics_after_cleanup(self):
        """Тест статистики после очистки"""
        logger.info("📊 Тестирование статистики ПОСЛЕ очистки...")
        
        stats = await self.payment_service.get_payment_statistics()
        
        logger.info("Статистика ПОСЛЕ очистки:")
        logger.info(f"  - Сегодня: {stats['today']['count']} платежей, {stats['today']['successful']} успешных")
        logger.info(f"  - Всего: {stats['total']['count']} платежей, {stats['total']['successful']} успешных")
        
        # Проверяем, что статистика не изменилась (только успешные платежи)
        assert stats['today']['successful'] == 1, f"Ожидался 1 успешный платеж, получено {stats['today']['successful']}"
        assert stats['today']['count'] == 1, f"Ожидался 1 платеж в статистике, получено {stats['today']['count']}"
        
        logger.info("✅ Статистика ПОСЛЕ очистки корректна")
        return stats
    
    async def test_database_state(self):
        """Проверка состояния базы данных"""
        logger.info("🗄️ Проверка состояния базы данных...")
        
        import aiosqlite
        async with aiosqlite.connect(self.db.db_path) as db:
            # Подсчитываем платежи по статусам
            cursor = await db.execute("""
                SELECT status, COUNT(*) 
                FROM payments 
                WHERE user_id = 999999999
                GROUP BY status
            """)
            status_counts = dict(await cursor.fetchall())
            
            logger.info("Платежи по статусам:")
            for status, count in status_counts.items():
                logger.info(f"  - {status}: {count}")
            
            # Проверяем ожидаемые результаты
            assert status_counts.get('completed', 0) == 1, "Должен быть 1 успешный платеж"
            assert status_counts.get('expired', 0) >= 2, "Должно быть минимум 2 просроченных платежа"
            assert status_counts.get('pending', 0) >= 1, "Должен остаться минимум 1 ожидающий платеж"
        
        logger.info("✅ Состояние базы данных корректно")
    
    async def cleanup_test_data(self):
        """Очистка тестовых данных"""
        logger.info("🧹 Очистка тестовых данных...")
        
        import aiosqlite
        async with aiosqlite.connect(self.db.db_path) as db:
            # Удаляем тестовые данные
            await db.execute("DELETE FROM payments WHERE user_id = 999999999")
            await db.execute("DELETE FROM users WHERE user_id = 999999999")
            await db.commit()
        
        logger.info("✅ Тестовые данные очищены")
    
    async def run_full_test(self):
        """Запуск полного теста"""
        logger.info("=" * 60)
        logger.info("🚀 ЗАПУСК ПОЛНОГО ТЕСТА СИСТЕМЫ ОЧИСТКИ ПЛАТЕЖЕЙ")
        logger.info("=" * 60)
        
        try:
            # Инициализация базы данных
            await self.db.create_tables_if_not_exist()
            
            # Создание тестовых данных
            await self.setup_test_data()
            
            # Тест статистики до очистки
            stats_before = await self.test_statistics_before_cleanup()
            
            # Тест процесса очистки
            cleanup_result = await self.test_cleanup_process()
            
            # Тест статистики после очистки
            stats_after = await self.test_statistics_after_cleanup()
            
            # Проверка состояния базы данных
            await self.test_database_state()
            
            # Очистка тестовых данных
            await self.cleanup_test_data()
            
            logger.info("=" * 60)
            logger.info("✅ ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!")
            logger.info("=" * 60)
            logger.info("🎯 ИСПРАВЛЕНИЯ РАБОТАЮТ КОРРЕКТНО:")
            logger.info("   ✅ Статистика показывает только успешные платежи")
            logger.info("   ✅ Просроченные инвойсы автоматически отменяются")
            logger.info("   ✅ Неоплаченные инвойсы не влияют на статистику")
            logger.info("   ✅ База данных остается чистой")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ ТЕСТ ПРОВАЛЕН: {e}")
            # Пытаемся очистить тестовые данные даже при ошибке
            try:
                await self.cleanup_test_data()
            except:
                pass
            return False

async def main():
    """Основная функция"""
    tester = PaymentCleanupTester()
    success = await tester.run_full_test()
    
    if success:
        print("\n🎉 Система готова к production!")
        print("   Можете запускать бота с исправленной статистикой платежей")
        sys.exit(0)
    else:
        print("\n💥 Обнаружены проблемы!")
        print("   Проверьте логи и исправьте ошибки перед запуском")
        sys.exit(1)

if __name__ == "__main__":
    # Проверяем Python версию
    if sys.version_info < (3, 8):
        print("❌ Требуется Python 3.8 или выше")
        sys.exit(1)
    
    # Запускаем тест
    asyncio.run(main())

#!/usr/bin/env python3
"""
Правильное исправление UniversalDatabase
Добавляет критически важные методы платежей в правильное место внутри класса
"""

import os
import re

def add_payment_methods_to_universal_database():
    """Добавляет только критически важные методы платежей в UniversalDatabase"""
    
    universal_file = "database/universal_database.py"
    
    if not os.path.exists(universal_file):
        print(f"❌ Файл {universal_file} не найден")
        return False
    
    # Читаем файл
    with open(universal_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Создаем резервную копию
    backup_file = f"{universal_file}.backup2"
    with open(backup_file, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"💾 Создана резервная копия: {backup_file}")
    
    # Методы платежей для добавления
    payment_methods = '''
    # ========== МЕТОДЫ ПЛАТЕЖЕЙ ==========
    
    async def create_payment(self, user_id: int, amount: int, currency: str = "RUB",
                           payment_id: str = None, invoice_payload: str = None,
                           subscription_months: int = 1) -> str:
        """Создать запись о платеже"""
        try:
            await self.adapter.connect()
            
            if self.adapter.db_type == 'sqlite':
                query = """
                    INSERT INTO payments (user_id, payment_id, amount, currency,
                                        invoice_payload, subscription_months)
                    VALUES (?, ?, ?, ?, ?, ?)
                """
                params = (user_id, payment_id, amount, currency, invoice_payload, subscription_months)
            else:  # PostgreSQL
                query = """
                    INSERT INTO payments (user_id, payment_id, amount, currency,
                                        invoice_payload, subscription_months)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id
                """
                params = (user_id, payment_id, amount, currency, invoice_payload, subscription_months)
            
            result = await self.adapter.execute(query, params)
            return str(result) if result else "1"
            
        except Exception as e:
            logger.error(f"Ошибка создания платежа: {e}")
            raise
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def get_payment(self, payment_id: str = None, db_id: int = None) -> Optional[dict]:
        """Получить платеж по ID"""
        try:
            await self.adapter.connect()
            
            if payment_id:
                if self.adapter.db_type == 'sqlite':
                    query = "SELECT * FROM payments WHERE payment_id = ?"
                    params = (payment_id,)
                else:  # PostgreSQL
                    query = "SELECT * FROM payments WHERE payment_id = $1"
                    params = (payment_id,)
            elif db_id:
                if self.adapter.db_type == 'sqlite':
                    query = "SELECT * FROM payments WHERE id = ?"
                    params = (db_id,)
                else:  # PostgreSQL
                    query = "SELECT * FROM payments WHERE id = $1"
                    params = (db_id,)
            else:
                return None
            
            result = await self.adapter.fetch_one(query, params)
            return dict(result) if result else None
            
        except Exception as e:
            logger.error(f"Ошибка получения платежа: {e}")
            return None
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def complete_payment(self, payment_id: str, provider_payment_id: str = None):
        """Завершить платеж и активировать подписку"""
        try:
            await self.adapter.connect()
            
            # Получаем информацию о платеже
            payment = await self.get_payment(payment_id=payment_id)
            if not payment:
                logger.error(f"Платеж {payment_id} не найден")
                return False
            
            # Обновляем статус платежа
            if self.adapter.db_type == 'sqlite':
                query = """
                    UPDATE payments 
                    SET status = 'completed', provider_payment_id = ?, completed_at = ?
                    WHERE payment_id = ?
                """
                params = (provider_payment_id, datetime.now(), payment_id)
            else:  # PostgreSQL
                query = """
                    UPDATE payments 
                    SET status = 'completed', provider_payment_id = $1, completed_at = $2
                    WHERE payment_id = $3
                """
                params = (provider_payment_id, datetime.now(), payment_id)
            
            await self.adapter.execute(query, params)
            
            # Активируем подписку пользователю
            end_date = datetime.now() + timedelta(days=30 * payment['subscription_months'])
            
            if self.adapter.db_type == 'sqlite':
                sub_query = """
                    UPDATE users
                    SET is_subscribed = TRUE, subscription_end = ?,
                        last_payment_date = ?, payment_provider = 'yookassa'
                    WHERE user_id = ?
                """
                sub_params = (end_date, datetime.now(), payment['user_id'])
            else:  # PostgreSQL
                sub_query = """
                    UPDATE users
                    SET is_subscribed = TRUE, subscription_end = $1,
                        last_payment_date = $2, payment_provider = 'yookassa'
                    WHERE user_id = $3
                """
                sub_params = (end_date, datetime.now(), payment['user_id'])
            
            await self.adapter.execute(sub_query, sub_params)
            return True
            
        except Exception as e:
            logger.error(f"Ошибка завершения платежа: {e}")
            return False
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def get_user_payments(self, user_id: int) -> List[dict]:
        """Получить все платежи пользователя"""
        try:
            await self.adapter.connect()
            
            if self.adapter.db_type == 'sqlite':
                query = """
                    SELECT * FROM payments
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                """
                params = (user_id,)
            else:  # PostgreSQL
                query = """
                    SELECT * FROM payments
                    WHERE user_id = $1
                    ORDER BY created_at DESC
                """
                params = (user_id,)
            
            results = await self.adapter.fetch_all(query, params)
            return [dict(row) for row in results] if results else []
            
        except Exception as e:
            logger.error(f"Ошибка получения платежей пользователя: {e}")
            return []
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def update_payment_status(self, payment_id: str, status: str):
        """Обновить статус платежа"""
        try:
            await self.adapter.connect()
            
            if self.adapter.db_type == 'sqlite':
                query = "UPDATE payments SET status = ? WHERE payment_id = ?"
                params = (status, payment_id)
            else:  # PostgreSQL
                query = "UPDATE payments SET status = $1 WHERE payment_id = $2"
                params = (status, payment_id)
            
            await self.adapter.execute(query, params)
            return True
            
        except Exception as e:
            logger.error(f"Ошибка обновления статуса платежа: {e}")
            return False
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass
'''
    
    # Находим конец класса UniversalDatabase (перед последней строкой с отступом)
    lines = content.split('\n')
    
    # Ищем последний метод класса
    insert_position = -1
    for i in range(len(lines) - 1, -1, -1):
        line = lines[i]
        if line.strip() and line.startswith('    ') and ('def ' in line or 'async def ' in line):
            # Находим конец этого метода
            for j in range(i + 1, len(lines)):
                next_line = lines[j]
                if (next_line.strip() and 
                    not next_line.startswith('    ') and 
                    not next_line.startswith('\t')):
                    insert_position = j
                    break
            if insert_position == -1:
                insert_position = len(lines)
            break
    
    if insert_position == -1:
        print("❌ Не удалось найти место для вставки методов")
        return False
    
    # Вставляем методы
    new_lines = lines[:insert_position] + payment_methods.split('\n') + lines[insert_position:]
    new_content = '\n'.join(new_lines)
    
    # Записываем обновленный файл
    with open(universal_file, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("✅ Критически важные методы платежей добавлены в UniversalDatabase")
    return True

if __name__ == "__main__":
    try:
        success = add_payment_methods_to_universal_database()
        
        if success:
            print("\n🎉 ИСПРАВЛЕНИЕ ЗАВЕРШЕНО УСПЕШНО!")
            print("📋 Добавлены критически важные методы:")
            print("   • create_payment")
            print("   • get_payment") 
            print("   • complete_payment")
            print("   • get_user_payments")
            print("   • update_payment_status")
            print("\n📋 Следующие шаги:")
            print("   1. Перезапустите бота")
            print("   2. Перезапустите админ-панель")
            print("   3. Протестируйте функциональность платежей")
        else:
            print("\n❌ Исправление не удалось")
            
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()

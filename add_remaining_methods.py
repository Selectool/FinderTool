#!/usr/bin/env python3
"""
Добавление всех оставшихся 36 методов в UniversalDatabase
Обеспечивает полную совместимость с админ-панелью
"""

import os
import re

def add_all_remaining_methods():
    """Добавляет все оставшиеся методы в UniversalDatabase"""
    
    universal_file = "database/universal_database.py"
    
    if not os.path.exists(universal_file):
        print(f"❌ Файл {universal_file} не найден")
        return False
    
    # Читаем файл
    with open(universal_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Создаем резервную копию
    backup_file = f"{universal_file}.backup3"
    with open(backup_file, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"💾 Создана резервная копия: {backup_file}")
    
    # Админ-функции
    remaining_methods = '''
    # ========== АДМИН-ФУНКЦИИ ==========

    async def create_admin_user(self, username: str, email: str, password_hash: str,
                              role: str = 'moderator', created_by: int = None) -> bool:
        """Создать админ пользователя"""
        try:
            await self.adapter.connect()

            if self.adapter.db_type == 'sqlite':
                query = """
                    INSERT INTO admin_users (username, email, password_hash, role, created_by, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """
                params = (username, email, password_hash, role, created_by, datetime.now())
            else:  # PostgreSQL
                query = """
                    INSERT INTO admin_users (username, email, password_hash, role, created_by, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """
                params = (username, email, password_hash, role, created_by, datetime.now())

            await self.adapter.execute(query, params)
            return True

        except Exception as e:
            logger.error(f"Ошибка создания админ пользователя: {e}")
            return False
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def get_admin_users(self) -> List[dict]:
        """Получить всех админ пользователей"""
        try:
            await self.adapter.connect()

            query = "SELECT * FROM admin_users WHERE is_active = TRUE ORDER BY created_at DESC"
            results = await self.adapter.fetch_all(query, ())
            return [dict(row) for row in results] if results else []

        except Exception as e:
            logger.error(f"Ошибка получения админ пользователей: {e}")
            return []
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def log_admin_action(self, admin_user_id: int, action: str, resource_type: str = None,
                             resource_id: int = None, details: str = None,
                             ip_address: str = None, user_agent: str = None) -> bool:
        """Логировать действие админа"""
        try:
            await self.adapter.connect()

            if self.adapter.db_type == 'sqlite':
                query = """
                    INSERT INTO audit_logs (admin_user_id, action, resource_type, resource_id,
                                          details, ip_address, user_agent, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """
                params = (admin_user_id, action, resource_type, resource_id,
                         details, ip_address, user_agent, datetime.now())
            else:  # PostgreSQL
                query = """
                    INSERT INTO audit_logs (admin_user_id, action, resource_type, resource_id,
                                          details, ip_address, user_agent, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """
                params = (admin_user_id, action, resource_type, resource_id,
                         details, ip_address, user_agent, datetime.now())

            await self.adapter.execute(query, params)
            return True

        except Exception as e:
            logger.error(f"Ошибка логирования действия админа: {e}")
            return False
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def get_audit_logs(self, page: int = 1, per_page: int = 50,
                           admin_user_id: int = None, action: str = None) -> dict:
        """Получить логи аудита"""
        try:
            await self.adapter.connect()

            offset = (page - 1) * per_page
            where_conditions = []
            params = []

            if admin_user_id:
                where_conditions.append("admin_user_id = ?")
                params.append(admin_user_id)

            if action:
                where_conditions.append("action = ?")
                params.append(action)

            where_clause = " WHERE " + " AND ".join(where_conditions) if where_conditions else ""

            # Получаем общее количество
            if self.adapter.db_type == 'sqlite':
                count_query = f"SELECT COUNT(*) FROM audit_logs{where_clause}"
                query = f"""
                    SELECT * FROM audit_logs{where_clause}
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """
                query_params = params + [per_page, offset]
            else:  # PostgreSQL
                pg_where_clause = where_clause
                for i, _ in enumerate(params):
                    pg_where_clause = pg_where_clause.replace('?', f'${i+1}', 1)

                count_query = f"SELECT COUNT(*) FROM audit_logs{pg_where_clause}"
                query = f"""
                    SELECT * FROM audit_logs{pg_where_clause}
                    ORDER BY created_at DESC
                    LIMIT ${len(params)+1} OFFSET ${len(params)+2}
                """
                query_params = params + [per_page, offset]

            count_result = await self.adapter.fetch_one(count_query, params)
            total = count_result[0] if count_result else 0

            results = await self.adapter.fetch_all(query, query_params)
            logs = [dict(row) for row in results] if results else []

            return {
                'logs': logs,
                'total': total,
                'page': page,
                'per_page': per_page,
                'pages': (total + per_page - 1) // per_page if total > 0 else 1
            }

        except Exception as e:
            logger.error(f"Ошибка получения логов аудита: {e}")
            return {'logs': [], 'total': 0, 'page': page, 'per_page': per_page, 'pages': 1}
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def get_user_activity_chart_data(self, days: int = 30) -> List[dict]:
        """Получить данные для графика активности пользователей"""
        try:
            await self.adapter.connect()

            if self.adapter.db_type == 'sqlite':
                query = """
                    SELECT DATE(created_at) as date, COUNT(*) as count
                    FROM users
                    WHERE created_at >= date('now', '-{} days')
                    GROUP BY DATE(created_at)
                    ORDER BY date
                """.format(days)
                params = ()
            else:  # PostgreSQL
                query = """
                    SELECT DATE(created_at) as date, COUNT(*) as count
                    FROM users
                    WHERE created_at >= NOW() - INTERVAL '%s days'
                    GROUP BY DATE(created_at)
                    ORDER BY date
                """
                params = (days,)

            results = await self.adapter.fetch_all(query, params)
            return [dict(row) for row in results] if results else []

        except Exception as e:
            logger.error(f"Ошибка получения данных активности: {e}")
            return []
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def get_blocked_users_count(self) -> int:
        """Получить количество заблокированных пользователей"""
        try:
            await self.adapter.connect()

            query = "SELECT COUNT(*) FROM users WHERE blocked = TRUE"
            result = await self.adapter.fetch_one(query, ())
            return result[0] if result else 0

        except Exception as e:
            logger.error(f"Ошибка получения количества заблокированных: {e}")
            return 0
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def _run_migrations(self) -> bool:
        """Запустить миграции"""
        try:
            # Этот метод может быть реализован позже
            # Пока возвращаем True для совместимости
            return True

        except Exception as e:
            logger.error(f"Ошибка выполнения миграций: {e}")
            return False

    print("✅ Добавлены админ-функции (7 методов)")
    return True

def add_admin_methods():
    """Добавляет админ-функции"""
    return add_all_remaining_methods()

if __name__ == "__main__":
    try:
        success = add_admin_methods()

        if success:
            print("\n🎉 АДМИН-ФУНКЦИИ ДОБАВЛЕНЫ!")
            print("📋 Добавлено 7 админ-методов")
        else:
            print("\n❌ Добавление не удалось")

    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()

    # Находим место для вставки (после методов управления пользователями)
    lines = content.split('\n')

    # Ищем конец последнего добавленного метода
    insert_position = -1
    for i, line in enumerate(lines):
        if ('get_users_by_role' in line and 'async def' in line) or ('update_user_role' in line and 'async def' in line):
            # Находим конец этого метода
            for j in range(i + 1, len(lines)):
                next_line = lines[j]
                if (next_line.strip() and
                    next_line.startswith('    ') and
                    ('async def' in next_line or 'def' in next_line)):
                    insert_position = j
                    break
            if insert_position == -1:
                # Ищем конец класса
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
    new_lines = lines[:insert_position] + remaining_methods.split('\n') + lines[insert_position:]
    new_content = '\n'.join(new_lines)

    # Записываем обновленный файл
    with open(universal_file, 'w', encoding='utf-8') as f:
        f.write(new_content)
        """Получить пользователей с пагинацией"""
        try:
            await self.adapter.connect()
            
            offset = (page - 1) * per_page
            where_conditions = []
            params = []
            
            if search:
                where_conditions.append("(username LIKE ? OR first_name LIKE ? OR last_name LIKE ?)")
                search_param = f"%{search}%"
                params.extend([search_param, search_param, search_param])
            
            if filter_type == 'subscribed':
                where_conditions.append("is_subscribed = TRUE")
            elif filter_type == 'blocked':
                where_conditions.append("blocked = TRUE")
            
            where_clause = " WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            
            # Получаем общее количество
            if self.adapter.db_type == 'sqlite':
                count_query = f"SELECT COUNT(*) FROM users{where_clause}"
                query = f"""
                    SELECT * FROM users{where_clause}
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """
                query_params = params + [per_page, offset]
            else:  # PostgreSQL
                # Конвертируем параметры для PostgreSQL
                pg_where_clause = where_clause
                for i, _ in enumerate(params):
                    pg_where_clause = pg_where_clause.replace('?', f'${i+1}', 1)
                
                count_query = f"SELECT COUNT(*) FROM users{pg_where_clause}"
                query = f"""
                    SELECT * FROM users{pg_where_clause}
                    ORDER BY created_at DESC
                    LIMIT ${len(params)+1} OFFSET ${len(params)+2}
                """
                query_params = params + [per_page, offset]
            
            count_result = await self.adapter.fetch_one(count_query, params)
            total = count_result[0] if count_result else 0
            
            results = await self.adapter.fetch_all(query, query_params)
            users = [dict(row) for row in results] if results else []
            
            return {
                'users': users,
                'total': total,
                'page': page,
                'per_page': per_page,
                'pages': (total + per_page - 1) // per_page if total > 0 else 1
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения пользователей: {e}")
            return {'users': [], 'total': 0, 'page': page, 'per_page': per_page, 'pages': 1}
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def get_all_users(self, limit: int = None) -> List[dict]:
        """Получить всех пользователей"""
        try:
            await self.adapter.connect()
            
            if self.adapter.db_type == 'sqlite':
                query = "SELECT * FROM users ORDER BY created_at DESC"
                if limit:
                    query += f" LIMIT {limit}"
                params = ()
            else:  # PostgreSQL
                query = "SELECT * FROM users ORDER BY created_at DESC"
                if limit:
                    query += f" LIMIT ${1}"
                    params = (limit,)
                else:
                    params = ()
            
            results = await self.adapter.fetch_all(query, params)
            return [dict(row) for row in results] if results else []
            
        except Exception as e:
            logger.error(f"Ошибка получения всех пользователей: {e}")
            return []
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def get_active_users(self, limit: int = None) -> List[dict]:
        """Получить активных пользователей"""
        try:
            await self.adapter.connect()
            
            if self.adapter.db_type == 'sqlite':
                query = """
                    SELECT * FROM users 
                    WHERE blocked = FALSE AND bot_blocked = FALSE
                    ORDER BY last_request DESC
                """
                if limit:
                    query += f" LIMIT {limit}"
                params = ()
            else:  # PostgreSQL
                query = """
                    SELECT * FROM users 
                    WHERE blocked = FALSE AND bot_blocked = FALSE
                    ORDER BY last_request DESC
                """
                if limit:
                    query += f" LIMIT ${1}"
                    params = (limit,)
                else:
                    params = ()
            
            results = await self.adapter.fetch_all(query, params)
            return [dict(row) for row in results] if results else []
            
        except Exception as e:
            logger.error(f"Ошибка получения активных пользователей: {e}")
            return []
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def get_subscribers(self, limit: int = None) -> List[dict]:
        """Получить подписчиков"""
        try:
            await self.adapter.connect()
            
            if self.adapter.db_type == 'sqlite':
                query = """
                    SELECT * FROM users 
                    WHERE is_subscribed = TRUE AND subscription_end > ?
                    ORDER BY subscription_end DESC
                """
                params = (datetime.now(),)
                if limit:
                    query += f" LIMIT {limit}"
            else:  # PostgreSQL
                query = """
                    SELECT * FROM users 
                    WHERE is_subscribed = TRUE AND subscription_end > $1
                    ORDER BY subscription_end DESC
                """
                params = (datetime.now(),)
                if limit:
                    query += f" LIMIT ${2}"
                    params = params + (limit,)
            
            results = await self.adapter.fetch_all(query, params)
            return [dict(row) for row in results] if results else []
            
        except Exception as e:
            logger.error(f"Ошибка получения подписчиков: {e}")
            return []
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def delete_user(self, user_id: int) -> bool:
        """Удалить пользователя"""
        try:
            await self.adapter.connect()
            
            if self.adapter.db_type == 'sqlite':
                query = "DELETE FROM users WHERE user_id = ?"
                params = (user_id,)
            else:  # PostgreSQL
                query = "DELETE FROM users WHERE user_id = $1"
                params = (user_id,)
            
            await self.adapter.execute(query, params)
            return True
            
        except Exception as e:
            logger.error(f"Ошибка удаления пользователя: {e}")
            return False
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def bulk_delete_users(self, user_ids: List[int]) -> bool:
        """Массовое удаление пользователей"""
        try:
            await self.adapter.connect()
            
            if not user_ids:
                return True
            
            placeholders = ','.join(['?' if self.adapter.db_type == 'sqlite' else f'${i+1}' for i in range(len(user_ids))])
            query = f"DELETE FROM users WHERE user_id IN ({placeholders})"
            
            await self.adapter.execute(query, user_ids)
            return True
            
        except Exception as e:
            logger.error(f"Ошибка массового удаления пользователей: {e}")
            return False
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def update_user_permissions(self, user_id: int, unlimited_access: bool = None, 
                                    blocked: bool = None, notes: str = None, blocked_by: int = None) -> bool:
        """Обновить права пользователя"""
        try:
            await self.adapter.connect()
            
            updates = []
            params = []
            
            if unlimited_access is not None:
                updates.append("unlimited_access = ?")
                params.append(unlimited_access)
            
            if blocked is not None:
                updates.append("blocked = ?")
                params.append(blocked)
                if blocked:
                    updates.append("blocked_at = ?")
                    params.append(datetime.now())
                    if blocked_by:
                        updates.append("blocked_by = ?")
                        params.append(blocked_by)
            
            if notes is not None:
                updates.append("notes = ?")
                params.append(notes)
            
            if not updates:
                return True
            
            if self.adapter.db_type == 'sqlite':
                query = f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?"
                params.append(user_id)
            else:  # PostgreSQL
                pg_updates = []
                for i, update in enumerate(updates):
                    pg_updates.append(update.replace('?', f'${i+1}'))
                query = f"UPDATE users SET {', '.join(pg_updates)} WHERE user_id = ${len(params)+1}"
                params.append(user_id)
            
            await self.adapter.execute(query, params)
            return True
            
        except Exception as e:
            logger.error(f"Ошибка обновления прав пользователя: {e}")
            return False
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def update_user_role(self, user_id: int, role: str) -> bool:
        """Обновить роль пользователя"""
        try:
            await self.adapter.connect()
            
            if self.adapter.db_type == 'sqlite':
                query = "UPDATE users SET role = ? WHERE user_id = ?"
                params = (role, user_id)
            else:  # PostgreSQL
                query = "UPDATE users SET role = $1 WHERE user_id = $2"
                params = (role, user_id)
            
            await self.adapter.execute(query, params)
            return True
            
        except Exception as e:
            logger.error(f"Ошибка обновления роли пользователя: {e}")
            return False
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass

    async def get_users_by_role(self, role: str) -> List[dict]:
        """Получить пользователей по роли"""
        try:
            await self.adapter.connect()
            
            if self.adapter.db_type == 'sqlite':
                query = "SELECT * FROM users WHERE role = ? ORDER BY created_at DESC"
                params = (role,)
            else:  # PostgreSQL
                query = "SELECT * FROM users WHERE role = $1 ORDER BY created_at DESC"
                params = (role,)
            
            results = await self.adapter.fetch_all(query, params)
            return [dict(row) for row in results] if results else []
            
        except Exception as e:
            logger.error(f"Ошибка получения пользователей по роли: {e}")
            return []
        finally:
            try:
                await self.adapter.disconnect()
            except:
                pass
'''
    
    # Находим место для вставки (после методов платежей)
    lines = content.split('\n')
    
    # Ищем конец методов платежей
    insert_position = -1
    for i, line in enumerate(lines):
        if 'update_payment_status' in line and 'async def' in line:
            # Находим конец этого метода
            for j in range(i + 1, len(lines)):
                next_line = lines[j]
                if (next_line.strip() and 
                    next_line.startswith('    ') and 
                    ('async def' in next_line or 'def' in next_line)):
                    insert_position = j
                    break
            if insert_position == -1:
                # Ищем конец класса
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
    new_lines = lines[:insert_position] + remaining_methods.split('\n') + lines[insert_position:]
    new_content = '\n'.join(new_lines)
    
    # Записываем обновленный файл
    with open(universal_file, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("✅ Добавлены методы управления пользователями (9 методов)")
    return True

if __name__ == "__main__":
    try:
        success = add_all_remaining_methods()
        
        if success:
            print("\n🎉 ПЕРВАЯ ЧАСТЬ МЕТОДОВ ДОБАВЛЕНА!")
            print("📋 Добавлено 9 методов управления пользователями")
            print("📋 Следующий шаг: добавить остальные группы методов")
        else:
            print("\n❌ Добавление не удалось")
            
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()

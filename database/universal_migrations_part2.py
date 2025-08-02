"""
Вторая часть универсальных миграций
"""

async def _create_ab_tests_table(self, adapter):
    """Создать таблицу A/B тестов"""
    if adapter.db_type == 'sqlite':
        query = """
            CREATE TABLE IF NOT EXISTS ab_tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                variant_a_content TEXT NOT NULL,
                variant_b_content TEXT NOT NULL,
                target_users TEXT DEFAULT 'all',
                status TEXT DEFAULT 'draft',
                variant_a_sent INTEGER DEFAULT 0,
                variant_b_sent INTEGER DEFAULT 0,
                variant_a_clicks INTEGER DEFAULT 0,
                variant_b_clicks INTEGER DEFAULT 0,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES admin_users (id)
            )
        """
    else:  # PostgreSQL
        query = """
            CREATE TABLE IF NOT EXISTS ab_tests (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                variant_a_content TEXT NOT NULL,
                variant_b_content TEXT NOT NULL,
                target_users VARCHAR(100) DEFAULT 'all',
                status VARCHAR(50) DEFAULT 'draft',
                variant_a_sent INTEGER DEFAULT 0,
                variant_b_sent INTEGER DEFAULT 0,
                variant_a_clicks INTEGER DEFAULT 0,
                variant_b_clicks INTEGER DEFAULT 0,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES admin_users (id)
            )
        """
    await adapter.execute(query)

async def _create_broadcast_logs_table(self, adapter):
    """Создать таблицу логов рассылок"""
    if adapter.db_type == 'sqlite':
        query = """
            CREATE TABLE IF NOT EXISTS broadcast_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                broadcast_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                message TEXT,
                error_details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (broadcast_id) REFERENCES broadcasts (id)
            )
        """
    else:  # PostgreSQL
        query = """
            CREATE TABLE IF NOT EXISTS broadcast_logs (
                id SERIAL PRIMARY KEY,
                broadcast_id INTEGER NOT NULL,
                user_id BIGINT NOT NULL,
                status VARCHAR(50) NOT NULL,
                message TEXT,
                error_details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (broadcast_id) REFERENCES broadcast_messages (id)
            )
        """
    await adapter.execute(query)
    
    # Создаем индексы
    await adapter.execute("""
        CREATE INDEX IF NOT EXISTS idx_broadcast_logs_broadcast_id
        ON broadcast_logs (broadcast_id)
    """)
    await adapter.execute("""
        CREATE INDEX IF NOT EXISTS idx_broadcast_logs_status
        ON broadcast_logs (broadcast_id, status)
    """)

async def _create_user_permissions_table(self, adapter):
    """Создать таблицу прав доступа пользователей"""
    if adapter.db_type == 'sqlite':
        query = """
            CREATE TABLE IF NOT EXISTS user_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                permission TEXT NOT NULL,
                granted_by INTEGER,
                granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES admin_users (id),
                FOREIGN KEY (granted_by) REFERENCES admin_users (id),
                UNIQUE(user_id, permission)
            )
        """
    else:  # PostgreSQL
        query = """
            CREATE TABLE IF NOT EXISTS user_permissions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                permission VARCHAR(255) NOT NULL,
                granted_by INTEGER,
                granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES admin_users (id),
                FOREIGN KEY (granted_by) REFERENCES admin_users (id),
                UNIQUE(user_id, permission)
            )
        """
    await adapter.execute(query)

async def _extend_users_table(self, adapter):
    """Расширить таблицу пользователей"""
    columns_to_add = [
        ("role", "TEXT DEFAULT 'user'" if adapter.db_type == 'sqlite' else "VARCHAR(100) DEFAULT 'user'"),
        ("unlimited_access", "BOOLEAN DEFAULT FALSE"),
        ("notes", "TEXT"),
        ("blocked", "BOOLEAN DEFAULT FALSE"),
        ("bot_blocked", "BOOLEAN DEFAULT FALSE"),
        ("blocked_at", "TIMESTAMP"),
        ("blocked_by", "INTEGER"),
        ("referrer_id", "INTEGER"),
        ("registration_source", "TEXT DEFAULT 'bot'" if adapter.db_type == 'sqlite' else "VARCHAR(100) DEFAULT 'bot'")
    ]
    
    for column_name, column_def in columns_to_add:
        try:
            await adapter.execute(f"ALTER TABLE users ADD COLUMN {column_name} {column_def}")
        except Exception as e:
            if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                continue  # Колонка уже существует
            else:
                print(f"Ошибка добавления колонки {column_name}: {e}")

async def _extend_broadcasts_table(self, adapter):
    """Расширить таблицу рассылок"""
    # Сначала проверим, какая таблица используется для рассылок
    if adapter.db_type == 'sqlite':
        table_name = "broadcasts"
    else:  # PostgreSQL
        table_name = "broadcast_messages"
    
    columns_to_add = [
        ("template_id", "INTEGER"),
        ("parse_mode", "TEXT DEFAULT 'HTML'" if adapter.db_type == 'sqlite' else "VARCHAR(50) DEFAULT 'HTML'"),
        ("target_users", "TEXT DEFAULT 'all'" if adapter.db_type == 'sqlite' else "VARCHAR(100) DEFAULT 'all'"),
        ("created_by", "INTEGER"),
        ("ab_test_id", "INTEGER"),
        ("scheduled_at", "TIMESTAMP"),
        ("started_at", "TIMESTAMP"),
        ("error_message", "TEXT")
    ]
    
    for column_name, column_def in columns_to_add:
        try:
            await adapter.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")
        except Exception as e:
            if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                continue  # Колонка уже существует
            else:
                print(f"Ошибка добавления колонки {column_name} в {table_name}: {e}")

async def _add_status_to_broadcasts(self, adapter):
    """Добавить статус к рассылкам"""
    table_name = "broadcasts" if adapter.db_type == 'sqlite' else "broadcast_messages"
    column_def = "TEXT DEFAULT 'pending'" if adapter.db_type == 'sqlite' else "VARCHAR(50) DEFAULT 'pending'"
    
    try:
        await adapter.execute(f"ALTER TABLE {table_name} ADD COLUMN status {column_def}")
    except Exception as e:
        if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
            pass  # Колонка уже существует
        else:
            print(f"Ошибка добавления колонки status: {e}")

async def _add_title_to_broadcasts(self, adapter):
    """Добавить заголовок к рассылкам"""
    if adapter.db_type == 'sqlite':
        table_name = "broadcasts"
        column_def = "TEXT"
    else:  # PostgreSQL
        table_name = "broadcast_messages"
        column_def = "VARCHAR(255)"
    
    try:
        await adapter.execute(f"ALTER TABLE {table_name} ADD COLUMN title {column_def}")
    except Exception as e:
        if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
            pass  # Колонка уже существует
        else:
            print(f"Ошибка добавления колонки title: {e}")

async def _insert_default_roles(self, adapter):
    """Вставить роли по умолчанию"""
    roles = [
        {
            'name': 'super_admin',
            'display_name': 'Супер Администратор',
            'permissions': '["*"]',
            'description': 'Полный доступ ко всем функциям системы'
        },
        {
            'name': 'admin',
            'display_name': 'Администратор',
            'permissions': '["users.view", "users.edit", "broadcasts.create", "broadcasts.send", "statistics.view", "templates.manage"]',
            'description': 'Управление пользователями и рассылками'
        },
        {
            'name': 'developer',
            'display_name': 'Разработчик',
            'permissions': '["statistics.view", "broadcasts.create", "templates.manage", "system.logs"]',
            'description': 'Доступ к статистике и тестированию'
        },
        {
            'name': 'moderator',
            'display_name': 'Модератор',
            'permissions': '["users.view", "statistics.view"]',
            'description': 'Только просмотр данных'
        }
    ]
    
    for role in roles:
        if adapter.db_type == 'sqlite':
            query = """
                INSERT OR IGNORE INTO roles (name, display_name, permissions, description)
                VALUES (?, ?, ?, ?)
            """
        else:  # PostgreSQL
            query = """
                INSERT INTO roles (name, display_name, permissions, description)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (name) DO NOTHING
            """
        
        await adapter.execute(query, (role['name'], role['display_name'], role['permissions'], role['description']))

async def _create_default_admin_user(self, adapter, pwd_context):
    """Создать пользователя админа по умолчанию"""
    # Проверяем, есть ли уже админ пользователи
    if adapter.db_type == 'sqlite':
        check_query = "SELECT COUNT(*) FROM admin_users"
    else:  # PostgreSQL
        check_query = "SELECT COUNT(*) FROM admin_users"
    
    result = await adapter.fetch_one(check_query)
    count = result[0] if result else 0
    
    if count == 0:
        # Создаем админа по умолчанию
        default_password = "admin123"
        password_hash = pwd_context.hash(default_password)
        
        if adapter.db_type == 'sqlite':
            query = """
                INSERT INTO admin_users (username, email, password_hash, role, is_active)
                VALUES (?, ?, ?, ?, ?)
            """
        else:  # PostgreSQL
            query = """
                INSERT INTO admin_users (username, email, password_hash, role, is_active)
                VALUES ($1, $2, $3, $4, $5)
            """
        
        await adapter.execute(query, ("admin", "admin@localhost", password_hash, "super_admin", True))
        
        print(f"Создан админ пользователь по умолчанию: admin / {default_password}")
        print("ОБЯЗАТЕЛЬНО измените пароль после первого входа!")

async def _add_telegram_user_roles(self, adapter):
    """Добавить роли для Telegram пользователей"""
    # Эта миграция уже выполнена в _extend_users_table
    pass

async def _assign_default_telegram_roles(self, adapter):
    """Назначить роли по умолчанию для Telegram пользователей"""
    user_roles = {
        5699315855: 'developer',      # Основной разработчик
        7610418399: 'senior_admin',   # Старший админ
        792247608: 'admin'            # Админ
    }
    
    for user_id, role in user_roles.items():
        # Проверяем, существует ли пользователь
        if adapter.db_type == 'sqlite':
            check_query = "SELECT user_id FROM users WHERE user_id = ?"
        else:  # PostgreSQL
            check_query = "SELECT user_id FROM users WHERE user_id = $1"
        
        result = await adapter.fetch_one(check_query, (user_id,))
        
        if result:
            # Обновляем роль существующего пользователя
            if adapter.db_type == 'sqlite':
                update_query = "UPDATE users SET role = ? WHERE user_id = ?"
            else:  # PostgreSQL
                update_query = "UPDATE users SET role = $1 WHERE user_id = $2"
            
            await adapter.execute(update_query, (role, user_id))
            print(f"Обновлена роль пользователя {user_id} на {role}")
        else:
            print(f"Пользователь {user_id} будет создан с ролью {role} при первом обращении")

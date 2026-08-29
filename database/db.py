import aiosqlite
from typing import Optional, List, Dict, Any
from datetime import datetime
import config

class Database:
    def __init__(self, db_path: str = config.DB_PATH):
        self.db_path = db_path

    async def init_db(self, initial_admins: Optional[List[int]] = None):
        """Инициализация таблиц базы данных и добавление начальных администраторов."""
        async with aiosqlite.connect(self.db_path) as db:
            # Таблица пользователей
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Таблица администраторов (с правами деанонимизации и админ-панели)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS admins (
                    user_id INTEGER PRIMARY KEY,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Таблица всех отправленных анонимных сообщений
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender_id INTEGER NOT NULL,
                    recipient_id INTEGER NOT NULL,
                    message_type TEXT NOT NULL,
                    content TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Таблица заблокированных пользователей
            await db.execute("""
                CREATE TABLE IF NOT EXISTS banned_users (
                    user_id INTEGER PRIMARY KEY,
                    reason TEXT,
                    banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Таблица диалогов с ИИ (строго изолирована для каждого админа)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS ai_chats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Таблица сообщений в диалогах с ИИ
            await db.execute("""
                CREATE TABLE IF NOT EXISTS ai_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await db.commit()

            # Добавляем админов из конфига при первом запуске
            if initial_admins:
                for admin_id in initial_admins:
                    await db.execute(
                        "INSERT OR IGNORE INTO admins (user_id) VALUES (?)",
                        (admin_id,)
                    )
                await db.commit()

    async def upsert_user(self, user_id: int, username: Optional[str], first_name: Optional[str], last_name: Optional[str]):
        """Сохранение или обновление информации о пользователе."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO users (user_id, username, first_name, last_name)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name,
                    last_name = excluded.last_name
            """, (user_id, username, first_name, last_name))
            await db.commit()

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получение информации о пользователе по его ID."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(row)
                return None

    async def get_all_users(self) -> List[Dict[str, Any]]:
        """Получение всех пользователей для рассылки."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT user_id, username, first_name FROM users") as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def get_total_users_count(self) -> int:
        """Получение общего количества пользователей."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM users") as cursor:
                res = await cursor.fetchone()
                return res[0] if res else 0

    async def get_new_users_today_count(self) -> int:
        """Количество новых пользователей за сегодня."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM users WHERE DATE(created_at) = DATE('now')") as cursor:
                res = await cursor.fetchone()
                return res[0] if res else 0

    async def add_message(self, sender_id: int, recipient_id: int, message_type: str, content: Optional[str] = None) -> int:
        """Сохранение отправленного сообщения в базу."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO messages (sender_id, recipient_id, message_type, content)
                VALUES (?, ?, ?, ?)
            """, (sender_id, recipient_id, message_type, content))
            await db.commit()
            return cursor.lastrowid

    async def get_message(self, message_id: int) -> Optional[Dict[str, Any]]:
        """Получение записи сообщения по его ID."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM messages WHERE id = ?", (message_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(row)
                return None

    async def get_total_messages_count(self) -> int:
        """Общее количество сообщений в боте."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM messages") as cursor:
                res = await cursor.fetchone()
                return res[0] if res else 0

    async def get_messages_today_count(self) -> int:
        """Количество сообщений за сегодня."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM messages WHERE DATE(created_at) = DATE('now')") as cursor:
                res = await cursor.fetchone()
                return res[0] if res else 0

    async def get_user_stats(self, user_id: int) -> Dict[str, int]:
        """Статистика сообщений конкретного пользователя."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM messages WHERE recipient_id = ?", (user_id,)) as cursor:
                received = (await cursor.fetchone())[0]
            async with db.execute("SELECT COUNT(*) FROM messages WHERE sender_id = ?", (user_id,)) as cursor:
                sent = (await cursor.fetchone())[0]
            return {"received": received, "sent": sent}

    async def get_user_received_today_count(self, user_id: int) -> int:
        """Количество полученных сообщений конкретного пользователя за сегодня."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM messages WHERE recipient_id = ? AND DATE(created_at) = DATE('now')",
                (user_id,)
            ) as cursor:
                res = await cursor.fetchone()
                return res[0] if res else 0

    async def get_recent_messages(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Получение всех последних сообщений для главного админа."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            query = """
                SELECT m.id, m.sender_id, m.recipient_id, m.message_type, m.content, m.created_at,
                       u_s.username AS sender_username, u_s.first_name AS sender_name,
                       u_r.username AS recipient_username, u_r.first_name AS recipient_name
                FROM messages m
                LEFT JOIN users u_s ON m.sender_id = u_s.user_id
                LEFT JOIN users u_r ON m.recipient_id = u_r.user_id
                ORDER BY m.id DESC
                LIMIT ?
            """
            async with db.execute(query, (limit,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def get_user_recent_messages(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Получение последних сообщений, адресованных только конкретному пользователю."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            query = """
                SELECT m.id, m.sender_id, m.recipient_id, m.message_type, m.content, m.created_at,
                       u_s.username AS sender_username, u_s.first_name AS sender_name,
                       u_r.username AS recipient_username, u_r.first_name AS recipient_name
                FROM messages m
                LEFT JOIN users u_s ON m.sender_id = u_s.user_id
                LEFT JOIN users u_r ON m.recipient_id = u_r.user_id
                WHERE m.recipient_id = ?
                ORDER BY m.id DESC
                LIMIT ?
            """
            async with db.execute(query, (user_id, limit)) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    # Методы для администраторов
    async def is_admin(self, user_id: int) -> bool:
        """Проверка, является ли пользователь администратором (из .env или БД)."""
        if user_id in config.ADMIN_IDS:
            return True
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)) as cursor:
                return (await cursor.fetchone()) is not None

    async def add_admin(self, user_id: int):
        """Добавление нового администратора в БД."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
            await db.commit()

    async def remove_admin(self, user_id: int):
        """Удаление администратора из БД."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
            await db.commit()

    async def get_all_admins(self) -> List[int]:
        """Получить список всех ID администраторов."""
        admins_set = set(config.ADMIN_IDS)
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT user_id FROM admins") as cursor:
                rows = await cursor.fetchall()
                for r in rows:
                    admins_set.add(r[0])
        return list(admins_set)

    # Методы для бана
    async def is_banned(self, user_id: int) -> bool:
        """Проверка, заблокирован ли пользователь."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT 1 FROM banned_users WHERE user_id = ?", (user_id,)) as cursor:
                return (await cursor.fetchone()) is not None

    async def ban_user(self, user_id: int, reason: str = "Нарушение правил"):
        """Блокировка пользователя."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO banned_users (user_id, reason)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET reason = excluded.reason
            """, (user_id, reason))
            await db.commit()

    async def unban_user(self, user_id: int):
        """Разблокировка пользователя."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM banned_users WHERE user_id = ?", (user_id,))
            await db.commit()

    async def get_banned_users(self) -> List[Dict[str, Any]]:
        """Получить список забаненных пользователей."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT b.user_id, b.reason, b.banned_at, u.username, u.first_name
                FROM banned_users b
                LEFT JOIN users u ON b.user_id = u.user_id
                ORDER BY b.banned_at DESC
            """) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    # ==========================================
    # Методы для изолированных AI-диалогов админов
    # ==========================================

    async def create_ai_chat(self, user_id: int, title: str = "Новый диалог") -> int:
        """Создать новый изолированный диалог для конкретного администратора."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO ai_chats (user_id, title)
                VALUES (?, ?)
            """, (user_id, title))
            await db.commit()
            return cursor.lastrowid

    async def get_user_ai_chats(self, user_id: int, limit: int = 30) -> List[Dict[str, Any]]:
        """Получить список всех сохраненных диалогов конкретного админа (чужие недоступны)."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            query = """
                SELECT c.id, c.user_id, c.title, c.created_at, c.updated_at,
                       COUNT(m.id) AS messages_count
                FROM ai_chats c
                LEFT JOIN ai_messages m ON c.id = m.chat_id
                WHERE c.user_id = ?
                GROUP BY c.id
                ORDER BY c.updated_at DESC
                LIMIT ?
            """
            async with db.execute(query, (user_id, limit)) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def get_ai_chat(self, chat_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """Получить конкретный диалог с проверкой владения (только свой)."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM ai_chats WHERE id = ? AND user_id = ?",
                (chat_id, user_id)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def update_ai_chat_title(self, chat_id: int, user_id: int, title: str):
        """Обновить заголовок диалога."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE ai_chats
                SET title = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND user_id = ?
            """, (title, chat_id, user_id))
            await db.commit()

    async def delete_ai_chat(self, chat_id: int, user_id: int):
        """Удалить диалог и все его сообщения."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM ai_messages WHERE chat_id = ? AND user_id = ?",
                (chat_id, user_id)
            )
            await db.execute(
                "DELETE FROM ai_chats WHERE id = ? AND user_id = ?",
                (chat_id, user_id)
            )
            await db.commit()

    async def add_ai_message(self, chat_id: int, user_id: int, role: str, content: str):
        """Сохранить сообщение в диалог."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO ai_messages (chat_id, user_id, role, content)
                VALUES (?, ?, ?, ?)
            """, (chat_id, user_id, role, content))
            await db.execute("""
                UPDATE ai_chats
                SET updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND user_id = ?
            """, (chat_id, user_id))
            await db.commit()

    async def get_ai_messages(self, chat_id: int, user_id: int, limit: int = 40) -> List[Dict[str, Any]]:
        """Получить историю сообщений диалога с проверкой владельца."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM ai_messages
                WHERE chat_id = ? AND user_id = ?
                ORDER BY id ASC
                LIMIT ?
            """, (chat_id, user_id, limit)) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

# Глобальный синглтон базы данных
db = Database()

import os
import aiosqlite
from datetime import datetime, timezone, timedelta

DB_PATH = os.getenv("DB_PATH", "database.db")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                api_key TEXT,
                is_banned INTEGER DEFAULT 0,
                is_approved INTEGER DEFAULT 0,
                expiry_date TEXT,
                total_purchased INTEGER DEFAULT 0,
                total_otps INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Schema migration jodi columns missing thake
        columns_to_add = [
            ("username", "TEXT"),
            ("full_name", "TEXT"),
            ("is_approved", "INTEGER DEFAULT 0"),
            ("expiry_date", "TEXT"),
            ("total_purchased", "INTEGER DEFAULT 0"),
            ("total_otps", "INTEGER DEFAULT 0")
        ]
        for col, col_type in columns_to_add:
            try:
                await db.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")
            except Exception:
                pass

        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS activations (
                activation_id TEXT PRIMARY KEY,
                user_id INTEGER,
                phone TEXT,
                message_id INTEGER
            )
        """)
        await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('maintenance', '0')")
        await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('restock_monitor', '1')")
        await db.commit()


async def add_user(user_id: int, username: str = None, full_name: str = None, is_approved: int = 0):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO users (user_id, username, full_name, is_approved) 
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET 
               username = COALESCE(?, users.username),
               full_name = COALESCE(?, users.full_name)""",
            (user_id, username, full_name, is_approved, username, full_name)
        )
        await db.commit()


async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
            return await cur.fetchone()


async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]


async def get_approved_users():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE is_approved = 1") as cur:
            return await cur.fetchall()


async def set_user_subscription(user_id: int, days: int = None):
    """Subscription set ba extend kore (days=None mane Lifetime)"""
    async with aiosqlite.connect(DB_PATH) as db:
        if days is None:
            expiry_str = "LIFETIME"
        else:
            exp_date = datetime.now(timezone.utc) + timedelta(days=days)
            expiry_str = exp_date.strftime("%Y-%m-%d %H:%M:%S")

        await db.execute(
            "UPDATE users SET is_approved = 1, expiry_date = ? WHERE user_id = ?",
            (expiry_str, user_id)
        )
        await db.commit()


async def extend_user_subscription(user_id: int, extra_days: int):
    """Current expiry-r shathe extra days jog kore"""
    user = await get_user(user_id)
    if not user:
        return False
    current_exp = user["expiry_date"]
    
    if not current_exp or current_exp == "LIFETIME":
        base_date = datetime.now(timezone.utc)
    else:
        try:
            base_date = datetime.strptime(current_exp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            if base_date < datetime.now(timezone.utc):
                base_date = datetime.now(timezone.utc)
        except Exception:
            base_date = datetime.now(timezone.utc)

    new_exp = (base_date + timedelta(days=extra_days)).strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET is_approved = 1, expiry_date = ? WHERE user_id = ?",
            (new_exp, user_id)
        )
        await db.commit()
    return new_exp


async def set_approval_status(user_id: int, is_approved: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET is_approved = ? WHERE user_id = ?",
            (1 if is_approved else 0, user_id)
        )
        await db.commit()


async def increment_user_stats(user_id: int, purchased: int = 0, otps: int = 0):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE users SET 
               total_purchased = total_purchased + ?,
               total_otps = total_otps + ?
               WHERE user_id = ?""",
            (purchased, otps, user_id)
        )
        await db.commit()


async def update_api_key(user_id: int, api_key: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET api_key = ? WHERE user_id = ?", (api_key, user_id))
        await db.commit()


async def set_ban_status(user_id: int, is_banned: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET is_banned = ? WHERE user_id = ?",
            (1 if is_banned else 0, user_id)
        )
        await db.commit()


async def get_setting(key: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else None


async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        await db.commit()


async def save_activation(activation_id: str, user_id: int, phone: str, message_id: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO activations (activation_id, user_id, phone, message_id) VALUES (?, ?, ?, ?)",
            (str(activation_id), user_id, phone, message_id)
        )
        await db.commit()


async def get_activation(activation_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM activations WHERE activation_id = ?", (str(activation_id),)) as cur:
            return await cur.fetchone()


async def delete_activation(activation_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM activations WHERE activation_id = ?", (str(activation_id),))
        await db.commit()

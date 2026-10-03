import os
import ssl
import asyncpg
from datetime import datetime, timezone, timedelta

DATABASE_URL = os.getenv("DATABASE_URL")
pool = None


async def get_pool():
    global pool
    if pool is None:
        if not DATABASE_URL:
            raise ValueError("DATABASE_URL environment variable is missing!")

        # Asyncpg-er jonno clean postgresql:// format toiri kora
        url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

        # Supabase Pooler-er IPv4 connection SSL context
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        pool = await asyncpg.create_pool(
            url,
            min_size=1,
            max_size=5,
            ssl=ctx
        )
    return pool


async def init_db():
    p = await get_pool()
    async with p.acquire() as conn:
        # PostgreSQL schema with auto-creation
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                api_key TEXT,
                is_banned INT DEFAULT 0,
                is_approved INT DEFAULT 0,
                expiry_date TEXT,
                total_purchased INT DEFAULT 0,
                total_otps INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS activations (
                activation_id TEXT PRIMARY KEY,
                user_id BIGINT,
                phone TEXT,
                message_id BIGINT
            )
        """)

        await conn.execute("""
            INSERT INTO settings (key, value) 
            VALUES ('maintenance', '0'), ('restock_monitor', '1')
            ON CONFLICT (key) DO NOTHING
        """)


async def add_user(user_id: int, username: str = None, full_name: str = None, is_approved: int = 0):
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute(
            """INSERT INTO users (user_id, username, full_name, is_approved) 
               VALUES ($1, $2, $3, $4)
               ON CONFLICT (user_id) DO UPDATE SET 
               username = COALESCE($2, users.username),
               full_name = COALESCE($3, users.full_name)""",
            user_id, username, full_name, is_approved
        )


async def get_user(user_id: int):
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
        return dict(row) if row else None


async def get_all_users():
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM users")
        return [r["user_id"] for r in rows]


async def get_approved_users():
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM users WHERE is_approved = 1")
        return [dict(r) for r in rows]


async def set_user_subscription(user_id: int, days: int = None):
    p = await get_pool()
    async with p.acquire() as conn:
        if days is None:
            expiry_str = "LIFETIME"
        else:
            exp_date = datetime.now(timezone.utc) + timedelta(days=days)
            expiry_str = exp_date.strftime("%Y-%m-%d %H:%M:%S")

        await conn.execute(
            "UPDATE users SET is_approved = 1, expiry_date = $1 WHERE user_id = $2",
            expiry_str, user_id
        )


async def extend_user_subscription(user_id: int, extra_days: int):
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
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute(
            "UPDATE users SET is_approved = 1, expiry_date = $1 WHERE user_id = $2",
            new_exp, user_id
        )
    return new_exp


async def set_approval_status(user_id: int, is_approved: bool):
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute(
            "UPDATE users SET is_approved = $1 WHERE user_id = $2",
            1 if is_approved else 0, user_id
        )


async def increment_user_stats(user_id: int, purchased: int = 0, otps: int = 0):
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute(
            """UPDATE users SET 
               total_purchased = total_purchased + $1,
               total_otps = total_otps + $2
               WHERE user_id = $3""",
            purchased, otps, user_id
        )


async def update_api_key(user_id: int, api_key: str):
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET api_key = $1 WHERE user_id = $2", api_key, user_id)


async def set_ban_status(user_id: int, is_banned: bool):
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute(
            "UPDATE users SET is_banned = $1 WHERE user_id = $2",
            1 if is_banned else 0, user_id
        )


async def get_setting(key: str):
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT value FROM settings WHERE key = $1", key)
        return row["value"] if row else None


async def set_setting(key: str, value: str):
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute(
            """INSERT INTO settings (key, value) VALUES ($1, $2)
               ON CONFLICT (key) DO UPDATE SET value = $2""",
            key, value
        )


async def save_activation(activation_id: str, user_id: int, phone: str, message_id: int = None):
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute(
            """INSERT INTO activations (activation_id, user_id, phone, message_id) 
               VALUES ($1, $2, $3, $4)
               ON CONFLICT (activation_id) DO UPDATE SET 
               user_id = $2, phone = $3, message_id = $4""",
            str(activation_id), user_id, phone, message_id
        )


async def get_activation(activation_id: str):
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM activations WHERE activation_id = $1", str(activation_id))
        return dict(row) if row else None


async def delete_activation(activation_id: str):
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM activations WHERE activation_id = $1", str(activation_id))

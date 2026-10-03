import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web

import database as db
from handlers import (
    handle_herosms_webhook,
    router,
    set_bot_instance,
    start_restock_monitor,
)

# Logger setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080))


async def start_web_server():
    """HeroSMS Webhook / Healthcheck Server for Render"""
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="HeroSMS Bot is running!"))
    app.router.add_get("/webhook", handle_herosms_webhook)
    app.router.add_post("/webhook", handle_herosms_webhook)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logging.info(f"Web server started on port {PORT}")


async def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN environment variable is not set!")

    # Initialize Database Schema
    await db.init_db()

    # Initialize Bot & Dispatcher
    bot = Bot(token=BOT_TOKEN)
    set_bot_instance(bot)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    # Start Background Restock Monitor Worker
    asyncio.create_task(start_restock_monitor())

    # Start Aiohttp Web Server (Render Web Service Port Binding)
    await start_web_server()

    logging.info("Bot is starting polling...")
    try:
        # Delete pending updates to prevent duplicate execution on restart
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped.")

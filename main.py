import asyncio
import logging
import sys

# Обеспечиваем корректный вывод UTF-8 (эмодзи) в консоли Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import socket
import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import BotCommand

import config
from database.db import db
from middlewares import BanCheckMiddleware
from handlers import user_router, anonymous_router, admin_router

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

async def set_bot_commands(bot: Bot):
    """Установка списка команд в меню бота."""
    commands = [
        BotCommand(command="start", description="🚀 Главное меню / Получить ссылку"),
        BotCommand(command="admin", description="⚡ Панель администратора"),
        BotCommand(command="id", description="🆔 Узнать свой Telegram ID"),
    ]
    try:
        await bot.set_my_commands(commands)
    except Exception as e:
        logger.warning(f"Не удалось установить команды бота: {e}")

async def main():
    logger.info("Запуск Telegram-бота анонимных вопросов...")

    # Проверка наличия токена бота
    if not config.BOT_TOKEN or config.BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        logger.error(
            "\n" + "=" * 60 + "\n"
            "❌ ОШИБКА: Токен бота не указан в файле .env!\n"
            "1. Откройте файл .env\n"
            "2. Вставьте ваш BOT_TOKEN=...\n"
            "3. Укажите ваши Telegram ID в ADMIN_IDS=...\n"
            "=" * 60
        )
        return

    # Инициализация базы данных
    await db.init_db(initial_admins=config.ADMIN_IDS)
    logger.info(f"База данных успешно инициализирована (Админы: {config.ADMIN_IDS})")

    # Сессия с поддержкой прокси при необходимости
    proxy = config.PROXY_URL if config.PROXY_URL else None
    if proxy:
        logger.info("Используется прокси для подключения к Telegram API")
        session = AiohttpSession(proxy=proxy)
    else:
        session = AiohttpSession()

    # Создание экземпляра бота и диспетчера
    bot = Bot(
        token=config.BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # Подключение мидлварей
    dp.message.middleware(BanCheckMiddleware())
    dp.callback_query.middleware(BanCheckMiddleware())

    # Подключение роутеров (хэндлеров)
    dp.include_router(admin_router)
    dp.include_router(anonymous_router)
    dp.include_router(user_router)

    # Установка команд в меню
    await set_bot_commands(bot)

    # Если бот запущен на Render/Heroku в качестве бесплатного Web Service, запускаем HTTP health check
    port = os.getenv("PORT")
    if port and port.isdigit():
        try:
            from aiohttp import web
            app = web.Application()
            app.router.add_get("/", lambda req: web.Response(text="Bot is running!"))
            app.router.add_get("/health", lambda req: web.Response(text="OK"))
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, "0.0.0.0", int(port))
            await site.start()
            logger.info(f"Health-check HTTP сервер запущен на порту {port} (для Render Free)")
        except Exception as e:
            logger.warning(f"Не удалось запустить health-check сервер: {e}")

    # Защита от засыпания Render (самопинг каждые 10 минут)
    render_url = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("APP_URL")
    if render_url:
        async def keep_alive(url: str):
            logger.info(f"Включен автопинг против засыпания Render: {url}")
            while True:
                await asyncio.sleep(600)  # каждые 10 минут
                try:
                    import urllib.request
                    urllib.request.urlopen(f"{url.rstrip('/')}/health", timeout=10)
                    logger.info("Keep-alive ping отправлен успешно!")
                except Exception:
                    pass

        asyncio.create_task(keep_alive(render_url))

    # Запуск поллинга
    try:
        bot_info = await bot.get_me()
        logger.info(f"Бот @{bot_info.username} успешно запущен и готов к работе!")
        # Удаляем вебхуки и пропускаем старые апдейты
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Критическая ошибка при работе бота: {e}")
    finally:
        await bot.session.close()
        logger.info("Бот остановлен.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот выключен пользователем.")

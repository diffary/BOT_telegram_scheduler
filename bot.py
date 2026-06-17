import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import BotCommand, Message

from config import Settings
from app.db.base import init_db, init_engine
from app.handlers import commands, tasks
from app.services.gemini import GeminiService
from app.services.scheduler import start_scheduler

# Команды, которые показываются в меню «/» в строке ввода Telegram.
BOT_COMMANDS = [
    BotCommand(command="start", description="Запуск / приветствие"),
    BotCommand(command="today", description="Задачи на сегодня"),
    BotCommand(command="list", description="Список задач"),
    BotCommand(command="timezone", description="Часовой пояс"),
    BotCommand(command="settings", description="Настройки и напоминания"),
    BotCommand(command="help", description="Помощь"),
]


async def main() -> None:
    # force=True: импорт google.genai мог уже сконфигурировать корневой логгер,
    # из-за чего обычный basicConfig стал бы no-op и INFO-логи пропали бы.
    logging.basicConfig(level=logging.INFO, force=True)
    settings = Settings()

    init_engine(settings.db_path)
    await init_db()

    bot = Bot(settings.bot_token)
    dp = Dispatcher()

    # Зависимости, доступные хендлерам по имени аргумента.
    dp["gemini"] = GeminiService(settings.gemini_api_key)
    dp["settings"] = settings

    @dp.message(CommandStart())
    async def start(message: Message) -> None:
        await message.answer(
            "Привет! Я ежедневник 🗓\n"
            "Напиши свободным текстом, что запланировано — например:\n"
            "«завтра в 15 встреча с врачом»"
        )

    dp.include_router(commands.router)
    dp.include_router(tasks.router)

    await bot.set_my_commands(BOT_COMMANDS)

    start_scheduler(bot, settings.tick_interval)

    logging.info("Bot started, polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import sys
from typing import Any, Dict
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import MenuButtonCommands
from dotenv import load_dotenv
import os
import handlers as handlers
from bot_mqtt_client import BotMqttClient, start

sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import logging
import logging_configurator
logger = logging_configurator.getLogger(__file__)

async def start_bot() -> None:
    os.environ.clear()
    load_dotenv()
    TOKEN = os.getenv("BOT_TOKEN")
    SERVER_IP = os.getenv("SERVER_IP")
    SERVER_PORT = int(os.getenv("SERVER_PORT"))

    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    await BotMqttClient.connect(server_ip=SERVER_IP, port=SERVER_PORT)
    # Run both the Telegram bot and MQTT listener in parallel
    await asyncio.gather(
        handlers.dp.start_polling(bot),
        start()
    )

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(start_bot())

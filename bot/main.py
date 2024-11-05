import asyncio
import logging
import sys
from typing import Any, Dict
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import MenuButtonCommands
from dotenv import load_dotenv
import os
from paho.mqtt.client import MQTTv311
import handlers as handlers
from bot_mqtt_client import BotMqttClient

# config_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'last_config.yml'))
configuration: Dict[str, Any] = {}
connected_nodes = {'ice': [], 'mini': []}
logger = logging.getLogger(__name__)
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

async def start_bot() -> None:
    bot_mqtt_client = BotMqttClient()
    # bot_mqtt_client = BotMqttClient("bot", os.getenv("SERVER_IP"), 1882)
    config_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'last_config.yml'))
    handlers.set_configuration(config_file_path)
    handlers.setup_mqtt_client(bot_mqtt_client)
    load_dotenv()
    TOKEN = os.getenv("BOT_TOKEN")
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    print("TG:\t" + config_file_path)
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    await handlers.dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)

    asyncio.run(start_bot())
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
from bot_mqtt_client import BotMqttClient, start


config_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'last_config.yml'))
configuration: Dict[int, Dict[str, Any]] = {}
connected_nodes = {'ice': [], 'mini': []}
logger = logging.getLogger(__name__)
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

BotMqttClient.connect()

async def start_bot() -> None:
    config_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'last_config.yml'))
    handlers.set_configuration(config_file_path)
    handlers.setup_mqtt_client(BotMqttClient)
    load_dotenv()
    TOKEN = os.getenv("BOT_TOKEN")
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    print("TG:\t" + config_file_path)
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    await handlers.dp.start_polling(bot)
    start()
    while True:
        pass

# async def start_bot() -> None:
#     start()

# async def main() -> None:
#     asyncio.gather(start_bot(), start_bot())

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(start_bot())
    # asyncio.run(main())
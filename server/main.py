import asyncio
import logging
import sys
from typing import Any, Dict
from aiogram import F, Dispatcher, Router, Bot, html
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart, Filter, Command, CommandObject
from aiogram.types import menu_button_default, MenuButtonDefault, MenuButtonCommands
from dotenv import load_dotenv
import yaml
import os
import paho.mqtt.client as paho
from paho import mqtt
from paho.mqtt.client import MQTTv311
import bot.handlers as handlers
from bot.bot_mqtt_client import BotMqttClient
from server_mqtt_client import ServerMqttClient

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

async def start_server() -> None:
    server_mqtt_client = ServerMqttClient("server")
    server_mqtt_client.subscribe("raspberry_pi")
    while True:
        pass
    #     if server_mqtt_client.received_messages["raspberry_pi"][-1] == "ready":
    #         print("SER:\tRaspberry Pi ready")
    #         for raspberry_id in range(1, 4):
    #             server_mqtt_client.publish(f"raspberry_{raspberry_id}_commander", "start")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    # asyncio.run(start_bot())
    asyncio.run(start_server())

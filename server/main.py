import asyncio
import logging
import sys
from typing import Any, Dict
from aiogram import F, Dispatcher, Router, Bot, html
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart, Filter, Command, CommandObject
from dotenv import load_dotenv
import yaml
import os
import paho.mqtt.client as paho
from paho import mqtt
from paho.mqtt.client import MQTTv311
import bot.handlers as handlers
from bot.bot_mqtt_client import BotMqttClient, ServerMqttClient
# config_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'last_config.yml'))

configuration: Dict[str, Any] = {}
connected_nodes = {'ice': [], 'mini': []}

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

async def start_bot() -> None:
    bot_mqtt_client = BotMqttClient("bot", os.getenv("SERVER_IP"), 1883)
    config_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'last_config.yml'))
    handlers.set_configuration(config_file_path)
    handlers.setup_mqtt_client(bot_mqtt_client)
    load_dotenv()
    TOKEN = os.getenv("BOT_TOKEN")
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    print(config_file_path)
    await handlers.dp.start_polling(bot)

async def start_server() -> None:
    server_mqtt_client = ServerMqttClient("server", os.getenv("SERVER_IP"), 1883)

    while True:
        time.sleep(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(start_bot())

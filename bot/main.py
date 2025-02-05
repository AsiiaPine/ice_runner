#!/usr/bin/env python3
# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import asyncio
import sys
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import MenuButtonCommands
from dotenv import load_dotenv
import os
import mqtt.handlers as mqtt_
import telegram.handlers as telegram_
from telegram.handlers import *
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import logging

# import logging_configurator

# logger = logging_configurator.getLogger(__file__)

async def start_bot() -> None:
    os.environ.clear()
    load_dotenv()
    TOKEN = os.getenv("BOT_TOKEN")
    SERVER_IP = os.getenv("SERVER_IP")
    SERVER_PORT = int(os.getenv("SERVER_PORT"))
    CHAT_ID = int(os.getenv("CHAT_ID"))
    telegram_.ChatIdFilter.CHAT_ID = CHAT_ID
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    await mqtt_.MqttClient.connect(server_ip=SERVER_IP, port=SERVER_PORT)
    mqtt_.add_handlers(mqtt_.MqttClient.client)
    # Run both the Telegram bot and MQTT listener in parallel
    await asyncio.gather(
        telegram_.dp.start_polling(bot),
        mqtt_.MqttClient.start()
    )

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(start_bot())

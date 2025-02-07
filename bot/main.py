"""The module is used to start the telegram bot with the specified chat id and its MQTT client"""

# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import asyncio
import sys
import os
import logging
from dotenv import load_dotenv
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import mqtt.handlers as mqtt_
import telegram.handlers as telegram_
from telegram.scheduler import Scheduler
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import logging_configurator

logger = logging_configurator.getLogger(__file__)

async def start_bot() -> None:
    os.environ.clear()
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    server_ip = os.getenv("SERVER_IP")
    server_port = int(os.getenv("SERVER_PORT"))
    chat_id = int(os.getenv("CHAT_ID"))
    telegram_.ChatIdFilter.chat_id = chat_id
    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    await mqtt_.MqttClient.connect(server_ip=server_ip, port=server_port)
    # Run both the Telegram bot and MQTT listener in parallel
    Scheduler.start(bot, chat_id)
    await asyncio.gather(
        telegram_.dp.start_polling(bot),
        mqtt_.MqttClient.start()
    )

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(start_bot())

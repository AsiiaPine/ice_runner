#!/usr/bin/env python3
# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

"""The script is used to start the telegram bot with the specified chat id and its MQTT client"""

import asyncio
import sys
import os
import logging

import argparse
from dotenv import load_dotenv
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import bot.mqtt.handlers as mqtt
import bot.telegram.handlers as telegram
from bot.telegram.scheduler import Scheduler
from common import logging_configurator
from aiogram.fsm.state import default_state

async def start_bot() -> None:
    os.environ.clear()
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    server_ip = os.getenv("SERVER_IP")
    server_port = int(os.getenv("SERVER_PORT"))
    chat_id = int(os.getenv("CHAT_ID"))
    telegram.RUNNER_ID = int(os.getenv("RUNNER_ID"))
    telegram.ChatIdFilter.chat_id = chat_id
    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    await mqtt.MqttClient.connect(server_ip=server_ip, port=server_port)
    # Run both the Telegram bot and MQTT listener in parallel
    Scheduler.start(bot, chat_id)
    await asyncio.gather(
        telegram.dp.start_polling(bot),
        mqtt.MqttClient.start()
    )

def start(log_dir: str, args: list['str'] = None) -> None:
    logging_configurator.get_logger(__file__, log_dir)
    parser = argparse.ArgumentParser()
    # Should just trip on non-empty arg and do nothing otherwise
    parser.parse_args(args)
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(start_bot())

if __name__ == "__main__":
    start(os.getcwd())

#!/usr/bin/env python3
# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

"""The script is used to start the telegram bot with the specified chat id and its MQTT client"""

import asyncio
import sys
import os
import logging
import signal

import argparse
from dotenv import load_dotenv
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import bot.mqtt.handlers as mqtt
import bot.telegram.handlers as telegram
from bot.telegram.scheduler import Scheduler
from common import logging_configurator

# Global variable to store tasks for cleanup
tasks = []

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    logging.info("Received interrupt signal, shutting down...")
    for task in tasks:
        if not task.done():
            task.cancel()
    # Don't exit immediately, let the asyncio event loop handle the cleanup

async def make_bot_task(bot: Bot) -> None:
    try:
        await telegram.dp.start_polling(bot)
    except asyncio.CancelledError:
        logging.info("Bot stopped")
    finally:
        await telegram.dp.stop_polling()
        logging.info("Bot finished")

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

    mqtt.MqttClient.connect(server_ip=server_ip, port=server_port)

    # Create tasks for all components
    scheduler_task = asyncio.create_task(Scheduler.start(bot, chat_id))
    bot_task = asyncio.create_task(make_bot_task(bot))
    mqtt_task = asyncio.create_task(mqtt.MqttClient.start())

    # Store tasks globally for signal handler
    global tasks
    tasks = [scheduler_task, bot_task, mqtt_task]

    # Set up callbacks for cleanup
    scheduler_task.add_done_callback(Scheduler.on_keyboard_interrupt)
    mqtt_task.add_done_callback(mqtt.MqttClient.on_keyboard_interrupt)

    try:
        # Wait for all tasks to complete
        logging.info("Jobs started")
        await asyncio.gather(scheduler_task, mqtt_task, bot_task)
    except asyncio.CancelledError:
        logging.info("Tasks cancelled, cleaning up...")
    except Exception as e:
        logging.error(f"Error in bot tasks: {e}")
    finally:
        # Ensure all tasks are cancelled
        logging.info("Cleanup completed")
        scheduler_task.cancel()
        bot_task.cancel()
        mqtt_task.cancel()
        await bot_task
        await scheduler_task
        await mqtt_task
        # Ensure all tasks are cleaned up before closing loop
        tasks.clear()

def start(log_dir: str, args: list['str'] = None) -> None:
    logging_configurator.get_logger(__file__, log_dir)
    parser = argparse.ArgumentParser()
    # Should just trip on non-empty arg and do nothing otherwise
    parser.parse_args(args)

    # # Set up signal handler for Ctrl+C
    # signal.signal(signal.SIGINT, signal_handler)
    # signal.signal(signal.SIGTERM, signal_handler)

    asyncio.run(start_bot())

if __name__ == "__main__":
    start(os.getcwd())

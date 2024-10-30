import asyncio
import logging
import re
import sys
import os
from os import getenv
import time
from typing import Any, Dict, List
from aiogram import Router, flags
from aiogram import F
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Filter, Command, CommandObject
from aiogram.types import Message
import yaml
from dotenv import load_dotenv

from bot.bot_mqtt_client import BotMqttClient

# from dronecan_communication.nodes_communicator import NodesCommunicator

configuration: Dict[str, Any] = {}
connected_nodes = {'ice': [], 'mini': []}
configuration_file_path: str = None
mqtt_client: BotMqttClient = None

def on_message(client, userdata, msg):
    print(msg.topic + ": " + msg.payload.decode())

def setup_mqtt_client(client: BotMqttClient) -> None:
    global mqtt_client
    mqtt_client = client
    mqtt_client.on_message = on_message

def set_configuration(path: str) -> None:
    global configuration_file_path
    global configuration
    configuration_file_path = path
    if not os.path.exists(configuration_file_path):
        return
    with open(configuration_file_path, "r") as file:
        configuration = yaml.safe_load(file)

# def get_configuration(config_file_path: str) -> Dict[str, Any]:
#     global configuration_file_path
#     configuration_file_path= config_file_path
#     if not os.path.exists(config_file_path):
#         return configuration
#     with open(config_file_path, "r") as file:
#         return yaml.safe_load(file)

def get_configuration_str(conf: Dict[str, Any] = None) -> str:
    conf_str = ""
    if conf:
        for name, value in conf.items():
            conf_str += f"\t{name}: {value}\n"
    return conf_str

# Bot token can be obtained via https://t.me/BotFather

# All handlers should be attached to the Router (or Dispatcher)
dp = Dispatcher()
form_router = Router()
dp.include_router(form_router)
# Define configuration message handling
class Conf(StatesGroup):
    conf_state = State()


@form_router.message(Conf.conf_state)
async def process_configuration(message: types.Message, state: FSMContext):
    """Process configuration of the runner"""
    print("Configuration started")
    print(message.text)
    matches = re.findall(r'--(\S+) (\d+)', message.text)
    for name, value in matches:
        configuration[name] = value
    await message.reply("Your configuration: " + get_configuration_str(configuration))
    with open(configuration_file_path, "w") as file:
        yaml.dump(configuration, file, default_flow_style=False)
    await message.reply(f"Configuration finished")
    await state.clear()

# Commands handlers
@dp.message(Command("conf"))
async def command_conf_handler(message: types.Message, state: FSMContext):
    await state.set_state(Conf.conf_state)
    await message.reply("Send me your configuration in format --name value")

# You can use state='*' if you want to handle all states
@form_router.message(Command("cancel"))
@form_router.message(F.text.casefold() == "cancel")
async def cancel_handler(message: Message, state: FSMContext) -> None:
    """
    Allow user to cancel any action
    """
    current_state = await state.get_state()
    if current_state is None:
        return

    logging.info("Cancelling state %r", current_state)
    await state.clear()
    await message.answer(
        "Cancelled.",
        reply_markup=ReplyKeyboardRemove(),
    )

@dp.message(Command("run"))
async def command_run_handler(message: Message) -> None:
    """
    This handler receives messages with `/run` command
    """
    await message.answer(f"Hello, print /help to know how to use me")
    if configuration is None:
        await message.answer(f"No configuration defined.")
    else:
        await message.answer("Chosen configuration: " + get_configuration_str(configuration))
        await message.answer(f"Send /cancel to abort the start sending. After start you can send /stop to stop")
    i = 0
    while i < 3:
        await message.answer(f"Starting in {3-i}")
        i += 1
        time.sleep(1)
    await message.answer(f"Started")
    await mqtt_client.publish("commander", "start")

@dp.message(Command("help"))
async def command_help_handler(message: Message) -> None:
    """
    This handler receives messages with `/help` command
    """
    await message.answer(
        "I can help you with the following commands:\n"
        "/conf - to configure the runner\n"
        "/cancel - to cancel any action\n"
        "/help - to get this message\n"
        "/run - to start the automatic running using the last configuration\n"
        "/start - to start the automatic ICE runner\n"
        "/status - to get the status of the connected ICE and current configuration\n"
        "/stop - to stop the automatic running immediately."
    )

@dp.message(Command("status"))
async def command_status_handler(message: Message) -> None:
    """
    This handler receives messages with `/status` command
    """
    await message.answer(f"Number of connected nodes: {len(connected_nodes)}")
    for node_type in connected_nodes:
        await message.answer(f"Number of {node_type} nodes: {len(connected_nodes[node_type])}")
    mqtt_client.publish("commander", "status")
    time.sleep(2)
    await message.answer("Current configuration: " + get_configuration_str(configuration))
    await message.answer(f"Nodes statuses:\n")
    for mqtt_topic in mqtt_client.received_messages.keys():
        if mqtt_topic.startswith("ice"):
            await message.answer(f"\t\t{mqtt_topic}: {mqtt_client.received_messages[mqtt_topic][-1]}")
        elif mqtt_topic.startswith("mini"):
            await message.answer(f"\t\t{mqtt_topic}: {mqtt_client.received_messages[mqtt_topic][-1]}")

@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    """
    This handler receives messages with `/start` command
    """
    print("Start handler")
    await message.answer(f"Hello, {html.bold(message.from_user.full_name)}!")
    if not configuration:
        print("No configuration stored")
        await message.answer(f"No configuration stored. Send configuration with /conf command")
    else:
        print("Configuration stored")
        await message.answer("Previous configuration: " + get_configuration_str(configuration))

@dp.message(Command("stop"))
async def command_stop_handler(message: Message) -> None:
    """
    This handler receives messages with `/stop` command
    """
    await message.answer(f"Stopping")
    
    await mqtt_client.publish("commander", "stop")

    await message.answer(f"Stopped")

async def main() -> None:
    # Initialize Bot instance with default bot properties which will be passed to all API calls
    load_dotenv()
    TOKEN = os.getenv("BOT_TOKEN")
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    print(configuration_file_path)
    dp.include_router(form_router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())

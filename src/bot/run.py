import asyncio
import logging
import re
import sys
import os
from os import getenv
import time
from typing import Dict, List
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

sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '../runner')))
from communication_with_nodes import NodesCommunicator

configuration = {}
connected_nodes = {'ice': [], 'mini': []}
communicator = NodesCommunicator(mes_timeout_sec=2.0)

config_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'last_config.yml'))

def get_configuration() -> Dict:
    with open(config_file_path, "r") as file:
        configuration = yaml.safe_load(file)

# Bot token can be obtained via https://t.me/BotFather
# os.environ['BOT_TOKEN'] = "7846364285:AAH_wuAUDgQtmUhyWOI4uyc6d-NWvM9w3Hs"
# TOKEN = getenv("BOT_TOKEN")
TOKEN = '7846364285:AAH_wuAUDgQtmUhyWOI4uyc6d-NWvM9w3Hs'
# All handlers should be attached to the Router (or Dispatcher)

dp = Dispatcher()
form_router = Router()

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
    await message.reply(f"Your configuration: {configuration}")
    with open(config_file_path, "w") as file:
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
    await message.answer(f"Hello, {html.bold(message.from_user.full_name)}!")
    if configuration is None:
        await message.answer(f"No configuration defined.")
    else:
        await message.answer(f"Chosen configuration: {configuration}")
        await message.answer(f"Send /stop to stop")
    i = 0
    while i < 3:
        await message.answer(f"Starting in {3-i}")
        i += 1
        time.sleep(1)

@dp.message(Command("help"))
async def command_help_handler(message: Message) -> None:
    """
    This handler receives messages with `/help` command
    """
    await message.answer(
        "I can help you with the following commands:\n"
        "/conf - to configure the runner\n"
        "/cancel - to cancel the configuration\n"
        "/help - to get this message\n"
        "/run - to start the automatic running\n"
        "/start - to start the automatic ICE runner\n"
        "/status - to get the status of the connected ICE\n"
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
    await message.answer(f"Current configuration: {configuration}")
    await message.answer(f"Nodes statuses:\n\tICE:")
    for status in communicator.get_ice_nodes_states():
        await message.answer(f"\t\t{status}")
    await message.answer(f"Nodes statuses:\n\tMini:")
    for status in communicator.get_mini_nodes_states():
        await message.answer(f"\t\t{status}")

@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    """
    This handler receives messages with `/start` command
    """
    configuration = get_configuration()
    await message.answer(f"Hello, {html.bold(message.from_user.full_name)}!")
    if not configuration:
        print("No configuration stored")
        await message.answer(f"No configuration stored. Send configuration with /conf command")
    else:
        print("Configuration stored")
        await message.answer(f"Previous configuration: {configuration}")

@dp.message(Command("stop"))
async def command_stop_handler(message: Message) -> None:
    """
    This handler receives messages with `/stop` command
    """
    await message.answer(f"Stopping")

async def main() -> None:
    # Initialize Bot instance with default bot properties which will be passed to all API calls
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    bot.forward_message(bot.get_me(), "Getting started")

    dp.include_router(form_router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())

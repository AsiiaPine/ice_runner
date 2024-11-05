import asyncio
import logging
import re
import sys
import os
import time
from typing import Any, Dict, List
from aiogram import Router, Bot, Dispatcher, types, F, html
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Filter, Command, CommandObject
from aiogram.types import Message
import yaml
from dotenv import load_dotenv

from bot_mqtt_client import BotMqttClient
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from common.RPStates import RPStates
import pprint

conf_params_description = '''
*rpm*:
    default: 4500
    description: Целевые обороты ДВС\n
*max-temperature*:
    default: 190
    description: Максимальная допустимая температура ДВС, после которой скрипт завершит выполнение\n
*max-gas-throttle*:
    dafeult: 100
    description: Максимальное допустимый уровень газовой заслонки в процентах. Значение 100 означает, что нет ограничений.\n
*report-period*:
    default: 600
    description: Период публикации статус сообщения в секундах \n
*chat-id*:
    default: None
    description: Идентификатор телеграм-чата, с которым бот будет взаимодействовать.\n
*time*:
    default: None
    description: Время в секундах, через которое скрипт автоматически закончит свое выполнение
*max-vibration*:
    default: None
    description: Максимальный допустимый уровень вибрации\n
*min-fuel-volume*:
    default: 0
    description: Минимальный уровень топлива (% или cm3), после которого прекращаем обкатку/выдаем предупреждение.
'''

commands_discription : Dict[str, str] = {
    "start": "Запускает автоматическую обкатку ДВС используя последние настроенные параметры/\nStart the automatic running using the last configuration\n",
    "status": "Получить статус подключенных блоков ДВС и текущие настройки/\nGet the status of the connected blocks and current configuration\n",
    "help": "Выдать список доступных команд/\nSend a list of available commands\n",
    "stop": "Остановить обкатку двигателей/\nStop the automatic running immediately\n",
    "conf": "Начать процесс настройки параметров\. После нажатия кнопки бот отправит сообщение с текущей конфигурацией и ждет в ответе новые параметры в формате \-\-имя значение\. Используйте комманду /cancel чтобы отменить конфигурирование и оставить старые параметры/\nStarts configuration process, after call you have specify configuration parameters in format \-\-name value\. Use /cancel to cancel the action\n",
    "cancel": "Отменить последнее действие/\nCancel any action\n"}

rp_id = None

configuration: Dict[int, Dict[str, Any]] = {}
configuration_file_path: str = None
mqtt_client = BotMqttClient

def set_configuration(path: str) -> None:
    global configuration_file_path
    global configuration
    configuration_file_path = path
    if not os.path.exists(configuration_file_path):
        return
    with open(configuration_file_path, "r") as file:
        configuration = yaml.safe_load(file)

def get_configuration_str(conf: Dict[str, Any] = None) -> str:
    conf_str = ""
    if conf:
        if pprint.isrecursive(conf):
            for rp_id, config in conf.items():
                conf_str += f"Raspberry Pi {rp_id} configuration:\n"
                for name, value in config.items():
                    conf_str += f"\t{name}: {value}\n"
            return conf_str
        for name, value in conf.items():
            conf_str += f"\t{name}: {value}\n"
        return conf_str

# Bot token can be obtained via https://t.me/BotFather

# All handlers should be attached to the Router (or Dispatcher)
dp = Dispatcher()
form_router = Router()
dp.include_router(form_router)

class RPConf(StatesGroup):
    rp_id = State()

class Conf(StatesGroup):
    conf_state = State()
    status_state = State()

@form_router.message(Conf.conf_state)
async def process_configuration(message: types.Message, state: FSMContext):
    """Process configuration of the runner"""
    if rp_id is None:
        await message.answer("Choose Raspberry Pi ID first. Print RP ID")
        state.set_state(RPConf.rp_id)
        return

    print("TG:\tConfiguration started")
    print("TG:\t" + message.text)
    matches = re.findall(r'--(\S+) (\d+)', message.text)
    if configuration[int(rp_id)] is None:
        configuration[int(rp_id)] = {}
    for name, value in matches:
        configuration[int(rp_id)][name] = value
    await message.reply("Your configuration: " + get_configuration_str(configuration[rp_id]))
    with open(configuration_file_path, "w") as file:
        yaml.dump(configuration, file, default_flow_style=False)
    await message.reply(f"Configuration finished")
    await state.clear()

@dp.message(Command(commands = ["chose_rp", "выбрать_ДВС"]))
async def choose_rp_id(message: types.Message, state: FSMContext) -> None:
    await state.set_state(RPConf.rp_id)
    print("Choose RP ID")
    await message.answer("Choose Raspberry Pi ID. Print RP ID")

@form_router.message(RPConf.rp_id)
async def choose_rp_id_handler(message: types.Message, state: FSMContext) -> None:
    if message.text not in mqtt_client.rp_status.keys():
        await message.answer("Raspberry Pi ID is not in the list")
        return
    global rp_id
    rp_id = int(message.text)
    print("Choose RP ID", rp_id)
    await state.clear()

# Commands handlers
@dp.message(Command(commands=["conf", "настроить_обкатку", "configure", "настройка"]))
async def command_conf_handler(message: types.Message, state: FSMContext):
    if rp_id is None:
        await message.answer("Choose Raspberry Pi ID first")
        state.set_state(RPConf.rp_id)
        return

    await state.set_state(Conf.conf_state)
    await message.reply("Send me your configuration in format --name value")
    await message.answer("Available parameters:\n" + conf_params_description)

# You can use state='*' if you want to handle all states
@form_router.message(Command(commands=["cancel", "отмена"]))
@form_router.message(F.text.casefold() == "cancel")
async def cancel_handler(message: Message, state: FSMContext) -> None:
    """
    Allow user to cancel any action
    """
    current_state = await state.get_state()
    if current_state is None:
        return
    logging.info("Cancelling state %r", current_state)
    print("Cancelling state", current_state)
    await state.update_data(Conf.status_state, None)
    await state.update_data(Conf.conf_state, None)

    # await state.clear()
    await message.answer(
        "Cancelled.",
        reply_markup=ReplyKeyboardRemove(),
    )

@dp.message(Command(commands=["run", "запустить"]))
async def command_run_handler(message: Message) -> None:
    """
    This handler receives messages with `/run` command
    """
    if configuration is None:
        await message.answer(f"No configuration defined.")
    else:
        await message.answer("Chosen rp_id: " + str(rp_id))
        await message.answer("Chosen configuration: " + get_configuration_str(configuration[rp_id]))
        await message.answer(f"Send /cancel to abort the running. After start you can send /stop to stop")
    i = 0
    while i < 3:
        await message.answer(f"Starting in {3-i}")
        i += 1
        time.sleep(1)
    await message.answer(f"Started")
    mqtt_client.client.publish("ice_runner/bot/usr_cmd/start", str(rp_id))

@dp.message(Command(commands=["help", "помощь"]))
async def command_help_handler(message: Message) -> None:
    """
    This handler receives messages with `/help` command
    """
    help_str = ''
    for command, description in commands_discription.items():
        help_str += f"\- *{command}*:\n\t{description}\n"
    await message.answer(
        "Список команд/ List of commands:\n" + help_str, parse_mode=ParseMode.MARKDOWN_V2)

@dp.message(Command(commands=["status", "статус"]))
async def command_status_handler(message: Message, state: FSMContext) -> None:
    """
    This handler receives messages with `/status` command
    """
    global rp_id
    await state.set_state(Conf.status_state)
    await message.answer(f"Number of connected ICE runners: {len(mqtt_client.rp_status.keys())}")
    print(f"Number of connected ICE runners: {len(mqtt_client.rp_status.keys())}")
    for rp_id, status in mqtt_client.rp_status.items():
        mqtt_client.client.publish("ice_runner/bot/usr_cmd/state", str(rp_id))
        print(f"\tRaspberry Pi {rp_id} status:\n")
        time.sleep(0.1)
        await message.answer(f"Raspberry Pi {rp_id} status:\n")
        await message.answer(f"\t{status}")
        if configuration[int(rp_id)] is None:
            await message.answer(f"No configuration for Raspberry Pi {rp_id}")
            return
    # await message.answer("Current configuration: " + get_configuration_str(configuration[int(rp_id)]))

@dp.message(CommandStart(ignore_case=True))
async def command_start_handler(message: Message) -> None:
    """
    This handler receives messages with `/start` command
    """
    print("TG:\tStart handler")
    await message.answer(f"Hello, {html.bold(message.from_user.full_name)}!")
    if not configuration:
        print("TG:\tNo configuration stored")
        await message.answer(f"No configuration stored. Send configuration with /conf command")
    else:
        print("TG:\tConfiguration stored")
        await message.answer("Previous configuration: " + get_configuration_str(configuration))
    await message.answer(f"Connected Raspberry Pi IDs:")
    for id, state in mqtt_client.rp_states.items():
        await message.answer(f"\t{id}: state - {state}")

@dp.message(Command(commands=["stop", "стоп"]))
async def command_stop_handler(message: Message) -> None:
    """
    This handler receives messages with `/stop` command
    """
    await message.answer(f"Stopping")
    await mqtt_client.client.publish("ice_runner/bot/usr_cmd/stop", f"{rp_id}")
    rp_status = int(mqtt_client.rp_status[rp_id])
    while True:
        if rp_status == RPStates.STOPPED.value:
            break
        await message.answer(f"Raspberry Pi {rp_id} is stopping. Current state: {rp_status.state}")
        time.sleep(1)
    await message.answer(f"Stopped")

async def main() -> None:
    # Initialize Bot instance with default bot properties which will be passed to all API calls
    load_dotenv()
    TOKEN = os.getenv("BOT_TOKEN")
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    print("TG:\t" + configuration_file_path)
    dp.include_router(form_router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())

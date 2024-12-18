import asyncio
import logging
import re
import sys
import os

from typing import Any, Dict, List, Tuple
from aiogram import Router, Bot, Dispatcher, types, F, html
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    ReplyKeyboardRemove,
)
from aiogram.fsm.storage.memory import MemoryStorage

from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message
import yaml
from dotenv import load_dotenv

from bot_mqtt_client import BotMqttClient
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from common.RPStates import RPStatesDict
import pprint
import time
from datetime import datetime, timezone
datetime.now(timezone.utc)

# import logging_configurator


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
    "/start": "Запускает автоматическую обкатку ДВС используя последние настроенные параметры/\nStart the automatic running using the last configuration\n",
    "/status": "Получить статус подключенных блоков ДВС и текущие настройки/\nGet the status of the connected blocks and current configuration\n",
    "/show_all": "Показать все состояния блоков ДВС/\nShow all states of connected blocks\n",
    "/help": "Выдать список доступных команд/\nSend a list of available commands\n",
    "/stop": "Остановить обкатку двигателей/\nStop the automatic running immediately\n",
    "/conf": "Начать процесс настройки параметров\. После нажатия кнопки бот отправит сообщение с текущей конфигурацией и ждет в ответе новые параметры в формате \-\-имя значение\. Используйте комманду /cancel чтобы отменить конфигурирование и оставить старые параметры/\nStarts configuration process, after call you have specify configuration parameters in format \-\-name value\. Use /cancel to cancel the action\n",
    "/cancel": "Отменить последнее действие/\nCancel any action\n"}

# rp_id = None
dp = Dispatcher(storage=MemoryStorage())
form_router = Router()
dp.include_router(form_router)

configuration: Dict[int, Dict[str, Any]] = {}
configuration_file_path: str = None
mqtt_client = BotMqttClient

def get_configuration_from_file(path: str) -> None:
    global configuration_file_path
    global configuration
    configuration_file_path = path
    if not os.path.exists(configuration_file_path):
        return
    with open(configuration_file_path, "r") as file:
        configuration = yaml.safe_load(file)

def get_configuration_str(rp_id: int) -> str:
    if rp_id not in mqtt_client.rp_configuration.keys():
        return "No configuration for Raspberry Pi " + str(rp_id)
    conf = mqtt_client.rp_configuration[int(rp_id)]
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

async def get_rp_status(rp_id: int, state: FSMContext) -> Tuple[Dict[str, Any], bool]:
    """The function sets the status of the Raspberry Pi and returns the status string and the state of the info was is updated"""
    await asyncio.sleep(0.4)
    data = await state.get_data()
    report_period = 10
    if "report_period" in data.keys():
        report_period = data["report_period"]
    last_status_update = time.time() - (report_period + 1)
    if "last_status_update" not in data.keys():
        data["last_status_update"] = last_status_update
        await state.set_data(data)
    elif data["last_status_update"] is not None:
        last_status_update = int(data["last_status_update"])
        if (time.time() - last_status_update) < report_period:
            return "\tNo new status from the node\n", False

    await asyncio.sleep(0.5)
    status = mqtt_client.rp_status[rp_id]
    rp_state = mqtt_client.rp_states[rp_id]
    mqtt_client.rp_status[rp_id] = None
    mqtt_client.rp_states[rp_id] = None
    if status is None:
        status_str = "\tNo status from the node\n"
    else:
        status_str = "\t\tState: " + rp_state + '\n'
        for name, value in list(status.items()):
            status_str += f"\t\t{name}: {value}\n"
    last_status_update = time.time()
    data["last_status_update"] = last_status_update
    await state.update_data(data)
    update_time = datetime.fromtimestamp(last_status_update).strftime('%Y-%m-%d %H:%M:%S') + '\n'
    return status_str + "\nupdate time: " + update_time, True

class Conf(StatesGroup):
    rp_id = State()
    conf_state = State()
    status_state = State()
    show_all_state = State()
    starting_state = State()

@form_router.message(Conf.conf_state)
async def process_configuration(message: types.Message, state: FSMContext):
    """Process configuration of the runner"""
    if "rp_id" not in (await state.get_data()).keys():  
        await message.answer("Выберите Raspberry Pi ID. Напишите RP ID")
        await state.set_state(Conf.rp_id)
        return
    rp_id = (await state.get_data())["rp_id"]
    matches = re.findall(r'--(\S+) (\d+)', message.text)
    if configuration[int(rp_id)] is None:
        configuration[int(rp_id)] = {}
    for name, value in matches:
        configuration[int(rp_id)][name] = value
    mqtt_client.client.publish(f"ice_runner/bot/configure/{rp_id}", conf_str)
    await asyncio.sleep(0.3)
    conf_str = get_configuration_str(rp_id)
    await message.reply("Your configuration: " + conf_str)
    await message.reply(f"Configuration finished")
    await state.clear()

@form_router.message(Command(commands=["chose_rp", "выбрать_ДВС"]))
async def choose_rp_id(message: types.Message, state: FSMContext) -> None:
    await state.set_state(Conf.rp_id)
    await message.answer("Выберите Raspberry Pi ID. Напишите RP ID")

@form_router.message(Conf.rp_id)
async def rp_id_handler(message: types.Message, state: FSMContext) -> None:
    if not message.text.isdigit():
        if message.text.casefold() in ("/cancel", "cancel"):
            await cancel_handler(message, state)
        else:
            await message.reply("Пожалуйста, введите числовой RP ID или отмените команду с помощью /cancel.")
        return
    rp_id_num = int(message.text)
    if rp_id_num not in mqtt_client.rp_status.keys():
        await message.reply("Raspberry Pi с таким ID не найден")
        return
    await message.reply(f"Выбранный Raspberry Pi ID: {rp_id_num}")
    await state.clear()
    await state.set_data({"rp_id": rp_id_num})

# Commands handlers
@dp.message(Command(commands=["conf", "настроить_обкатку", "configure", "настройка"]))
async def command_conf_handler(message: types.Message, state: FSMContext):
    if "rp_id" not in (await state.get_data()).keys():
        await message.answer("Выберите Raspberry Pi ID. Напишите RP ID")
        state.set_state(Conf.rp_id)
        return

    await state.set_state(Conf.conf_state)
    await message.reply("Send me your configuration in format --name value")
    await message.answer("Available parameters:\n" + conf_params_description)

# You can use state='*' if you want to handle all states
@form_router.message(Command(commands=["cancel", "отмена"]))
async def cancel_handler(message: Message, state: FSMContext) -> None:
    """
    Allow user to cancel any action
    """
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Нет активных действий для отмены.", reply_markup=ReplyKeyboardRemove())
        return

    logging.getLogger(__name__).info("Cancelling state %r", current_state)
    await state.clear()
    await message.answer(
        "Cancelled.",
        reply_markup=ReplyKeyboardRemove(),
    )

@form_router.message(Command(commands=["run", "start", "запустить"], ignore_case=True))
async def command_run_handler(message: Message, state: FSMContext) -> None:
    """
    This handler receives messages with `/run` command
    """
    if "rp_id" not in (await state.get_data()).keys():
        await message.answer("Выберите Raspberry Pi ID. Напишите RP ID")
        await state.set_state(Conf.rp_id)
        return
    rp_id = (await state.get_data())["rp_id"]
    await message.answer("Выбранная Raspberry Pi ID: " + str(rp_id))
    await message.answer("Конфигурация обкатки: " + get_configuration_str(rp_id))
    await message.answer(f"Отправьте /cancel или /отмена чтобы отменить запуск обкатки. После запуска отправьте /stop или /стоп чтобы остановить ее")
    i = 0
    await state.set_state(Conf.starting_state)
    is_starting = await state.get_state()
    print(is_starting)
    logging.getLogger(__name__).info(f"STATUS\t| received CMD START from user {message.from_user.username}")
    while i < 10 and is_starting:
        await message.answer(f"Запуск через {10-i}")
        i += 1
        await asyncio.sleep(1)
        is_starting = await state.get_state()
        if is_starting is None:
            logging.getLogger(__name__).info(f"STATUS\t| CMD START aborted by user")
            await asyncio.sleep(0.1)
            continue
    if is_starting:
        await message.answer(f"Запущено")
        logging.getLogger(__name__).info(f"STATUS\t| CMD START send to Raspberry Pi {rp_id}")
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
        "Список команд/ List of commands:\n" + help_str, parse_mode=ParseMode.HTML)

@dp.message(Command(commands=["show_all", "показать_все"]))
async def command_show_all_handler(message: Message, state: FSMContext) -> None:
    """
    This handler receives messages with `/show_all` command
    """
    mqtt_client.client.publish("ice_runner/bot/usr_cmd/who_alive")
    await state.set_state(Conf.show_all_state)
    await asyncio.sleep(1)
    messages: List[Dict[str, Any]] = []
    message_text = ""
    connected_nodes = mqtt_client.rp_status.keys()
    await message.answer(f"Number of connected ICE runners: {len(connected_nodes)}")
    if len(connected_nodes) == 0:
        return

    for rp_id in mqtt_client.rp_states.keys():
        print(f"Showing status for {rp_id}")
        mqtt_client.client.publish("ice_runner/bot/usr_cmd/config", str(rp_id))
        await asyncio.sleep(0.3)
        header_str = html.bold(f"Raspberry Pi ID: {rp_id}\n\tStatus:\n" )
        report_period = 10
        data = await state.get_data()
        if mqtt_client.rp_configuration[int(rp_id)] is None:
            conf_str = html.bold("\tNo configuration stored\n")
        else:
            report_period = int(mqtt_client.rp_configuration[int(rp_id)]["report_period"])
            conf_str = html.bold("\tCurrent configuration:\n") + get_configuration_str(rp_id)
        data["rp_id"] = rp_id
        data["report_period"] = report_period
        await state.set_data(data)
        status_str, is_updated = await get_rp_status(int(rp_id), state)
        conf_str = ""
        message_text += (header_str + status_str + conf_str)
        # res = await message.answer(message_text, parse_mode=ParseMode.HTML)
        messages.append({"rp_id": rp_id, "header": header_str, "status": status_str, "conf": conf_str})
        await asyncio.sleep(0.3)
    res = await message.answer(message_text, parse_mode=ParseMode.HTML)
    await state.set_data({})

@form_router.message(Command(commands=["status", "статус"]))
async def command_status_handler(message: Message, state: FSMContext) -> None:
    """
    This handler receives messages with `/status` command
    """
    await state.set_state()
    await state.set_state(Conf.status_state)
    data = await state.get_data()
    data["last_status_update"] = None
    if "rp_id" not in data.keys():
        await message.answer("Выберите Raspberry Pi ID. Напишите RP ID. Чтобы получить список ID нажмите /show_all")
        await state.set_state(Conf.rp_id)
        return
    rp_id = data["rp_id"]

    mqtt_client.client.publish("ice_runner/bot/usr_cmd/config", str(rp_id))
    mqtt_client.client.publish("ice_runner/bot/usr_cmd/state", str(rp_id))
    mqtt_client.client.publish("ice_runner/bot/usr_cmd/status", str(rp_id))
    await asyncio.sleep(0.3)

    header_str = html.bold(f"Raspberry Pi ID: {rp_id}\n\tStatus:\n")

    if rp_id not in mqtt_client.rp_configuration.keys():
        conf_str = html.bold("\tNo configuration stored")
    else:
        conf_result = get_configuration_str(int(rp_id))
        if conf_result:
            conf_str = html.bold("\tCurrent configuration:\n") + conf_result
        if "report_period" not in data.keys():
            if "report_period" in mqtt_client.rp_configuration[int(rp_id)].keys():
                report_period = int(mqtt_client.rp_configuration[int(rp_id)]["report_period"])
            else:
                report_period = 10
            data["report_period"] = report_period
    await state.set_data(data)
    status_str, is_updated = await get_rp_status(rp_id, state)

    message_text = (header_str + status_str + conf_str)
    res = await message.answer(message_text, parse_mode=ParseMode.HTML)
    await asyncio.sleep(0.5)
    while ((await state.get_state()) == Conf.status_state):
        print("Updating status ", await state.get_data())
        status_str, is_updated = await get_rp_status(rp_id, state)
        if not is_updated:
            continue
        message_text = (header_str + status_str + conf_str)
        response = await res.edit_text(message_text, parse_mode=ParseMode.HTML)
        await asyncio.sleep(0.5)

@form_router.message(Command(commands=["stop", "стоп"]))
async def command_stop_handler(message: Message, state: FSMContext) -> None:
    """
    This handler receives messages with `/stop` command
    """
    if "rp_id" not in (await state.get_data()).keys():
        await message.answer("Выберите Raspberry Pi ID. Напишите RP ID")
        await state.set_state(Conf.rp_id)
        return
    await message.answer(f"Stopping")
    rp_id = (await state.get_data())["rp_id"]
    mqtt_client.client.publish("ice_runner/bot/usr_cmd/stop", f"{rp_id}")
    mqtt_client.client.publish("ice_runner/bot/usr_cmd/stop", f"{rp_id}")
    rp_status = int(mqtt_client.rp_status[rp_id]["state"])
    while True:
        if rp_status != RPStatesDict["RUNNING"]:
            break
        state = list(RPStatesDict.keys())[list(RPStatesDict.values()).index(int(BotMqttClient.rp_states[rp_status["state"]]))]
        await message.answer(f"Raspberry Pi {rp_id} is stopping. Current state: {state}")
        mqtt_client.client.publish("ice_runner/bot/usr_cmd/stop", f"{rp_id}")
        await asyncio.sleep(1)
    await message.answer(f"Stopped")

@form_router.message(Command(commands=["server", "сервер"]))
async def command_server(message: Message, state: FSMContext) -> None:
    """
    This handler receives messages with `/server` command
    """
    await message.answer("Проверяем работу сервера")
    BotMqttClient.client.publish("ice_runner/bot/usr_cmd/server", "server")
    await asyncio.sleep(1)
    if BotMqttClient.server_connected:
        await message.answer("Сервер подключен")
    else:
        await message.answer("Сервер не подключен")

@form_router.message(F.text.lower().not_in(commands_discription.keys()))
async def unknown_message(msg: types.Message):
    message_text = 'Я не знаю, что с этим делать :astonished: \nЯ просто напомню, что есть команда /help'
    await msg.reply(message_text, parse_mode=ParseMode.HTML)

async def main() -> None:
    # Initialize Bot instance with default bot properties which will be passed to all API calls
    load_dotenv()
    TOKEN = os.getenv("BOT_TOKEN")
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    print("TG:\t" + configuration_file_path)
    logging.getLogger(__name__).info(f"STATUS\t| Bot started")
    dp.include_router(form_router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

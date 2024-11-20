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
    Message,
    ReplyKeyboardRemove,
)
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
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
    "/start": "Запускает автоматическую обкатку ДВС используя последние настроенные параметры/\nStart the automatic running using the last configuration\n",
    "/status": "Получить статус подключенных блоков ДВС и текущие настройки/\nGet the status of the connected blocks and current configuration\n",
    "/show_all": "Показать все состояния блоков ДВС/\nShow all states of connected blocks\n",
    "/help": "Выдать список доступных команд/\nSend a list of available commands\n",
    "/stop": "Остановить обкатку двигателей/\nStop the automatic running immediately\n",
    "/conf": "Начать процесс настройки параметров\. После нажатия кнопки бот отправит сообщение с текущей конфигурацией и ждет в ответе новые параметры в формате \-\-имя значение\. Используйте комманду /cancel чтобы отменить конфигурирование и оставить старые параметры/\nStarts configuration process, after call you have specify configuration parameters in format \-\-name value\. Use /cancel to cancel the action\n",
    "/cancel": "Отменить последнее действие/\nCancel any action\n"}

rp_id = None

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

async def get_rp_status(rp_id: int) -> Dict[str, Any]:
    mqtt_client.client.publish("ice_runner/bot/usr_cmd/state", str(rp_id))
    mqtt_client.client.publish("ice_runner/bot/usr_cmd/stats", str(rp_id))
    await asyncio.sleep(0.4)
    if rp_id not in mqtt_client.rp_status.keys():
        return "\tNo status from the node\n"
    status = mqtt_client.rp_status[rp_id]
    mqtt_client.rp_status.__delitem__(rp_id)
    status_str = "\t\tState: " + RPStates(status["state"]).name + '\n'
    for name, value in status.items():
        status_str += f"\t\t{name}: {value}\n"
    return status_str + "\nupdate time: " + time.strftime("%Y-%m-%d %H:%M:%S\n")

dp = Dispatcher()
form_router = Router()
dp.include_router(form_router)

class Conf(StatesGroup):
    rp_id = State()
    conf_state = State()
    status_state = State()
    show_all_state = State()

@form_router.message(Conf.conf_state)
async def process_configuration(message: types.Message, state: FSMContext):
    """Process configuration of the runner"""
    if rp_id is None:
        await message.answer("Выберите Raspberry Pi ID. Напишите RP ID")
        state.set_state(Conf.rp_id)
        return

    print("TG:\tConfiguration started")
    print("TG:\t" + message.text)
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
    print("Choose RP ID")
    await message.answer("Выберите Raspberry Pi ID. Напишите RP ID")

@form_router.message(Conf.rp_id)
async def choose_rp_id_handler(message: types.Message, state: FSMContext) -> None:
    print("Configure RP ID")
    if int(message.text) not in mqtt_client.rp_status.keys():
        await message.reply("Raspberry Pi с таким ID не найден")
        return
    global rp_id
    rp_id = int(message.text)
    await message.reply(f"Выбранный Raspberry Pi ID: {rp_id}")
    await state.clear()

# Commands handlers
@dp.message(Command(commands=["conf", "настроить_обкатку", "configure", "настройка"]))
async def command_conf_handler(message: types.Message, state: FSMContext):
    if rp_id is None:
        await message.answer("Выберите Raspberry Pi ID. Напишите RP ID")
        state.set_state(Conf.rp_id)
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
    await state.update_data({"status_state": None, "conf_state": None})
    # await state.update_data(Conf.conf_state, None)

    # await state.clear()
    await message.answer(
        "Cancelled.",
        reply_markup=ReplyKeyboardRemove(),
    )

@form_router.message(Command(commands=["run", "start", "запустить"], ignore_case=True))
async def command_run_handler(message: Message, state: FSMContext) -> None:
    """
    This handler receives messages with `/run` command
    """
    if rp_id is None:
        await message.answer("Выберите Raspberry Pi ID. Напишите RP ID")
        await state.set_state(Conf.rp_id)
        return
    await message.answer("Выбранная Raspberry Pi ID: " + str(rp_id))
    await message.answer("Конфигурация обкатки: " + get_configuration_str(rp_id))
    await message.answer(f"Отправьте /cancel или /отмена чтобы отменить запуск обкатки. После запуска отправьте /stop или /стоп чтобы остановить ее")
    i = 0
    while i < 3:
        await message.answer(f"Запуск через {3-i}")
        i += 1
        time.sleep(1)
    await message.answer(f"Запущено")
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

    await state.update_data({"status_state" : None}) 
    await state.set_state(Conf.show_all_state)
    messages: List[Dict[str, Any]] = []
    report_period = 10
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
        status_str = await get_rp_status(int(rp_id))
        conf_str = ""
        if mqtt_client.rp_configuration[int(rp_id)] is None:
            conf_str = html.bold("\tNo configuration stored\n")
        else:
            conf_str = html.bold("\tCurrent configuration:\n") + get_configuration_str(rp_id)
        message_text += (header_str + status_str + conf_str)
        # res = await message.answer(message_text, parse_mode=ParseMode.HTML)
        messages.append({"rp_id": rp_id, "header": header_str, "status": status_str, "conf": conf_str})
        await asyncio.sleep(0.3)
    res = await message.answer(message_text, parse_mode=ParseMode.HTML)
    prev_time = 0
    while Conf.show_all_state:
        if time.time() - prev_time > report_period:
            print("Updating status")
            message_text = ""
            for rp_mes in messages:
                rp_mes["status"] = await get_rp_status(rp_mes["rp_id"])
                message_text += (rp_mes["header"] + rp_mes["status"] + rp_mes["conf"])
                await asyncio.sleep(0.3)
            res.edit_text(message_text, parse_mode=ParseMode.HTML)
            prev_time = time.time()

@form_router.message(Command(commands=["status", "статус"]))
async def command_status_handler(message: Message, state: FSMContext) -> None:
    """
    This handler receives messages with `/status` command
    """
    global rp_id
    report_period = 10
    if rp_id is None:
        await message.answer("Выберите Raspberry Pi ID. Напишите RP ID")
        await state.set_state(Conf.rp_id)
        return
    await state.update_data({"show_all_state": None})

    await state.set_state(Conf.status_state)
    mqtt_client.client.publish("ice_runner/bot/usr_cmd/config", str(rp_id))
    await asyncio.sleep(0.3)

    header_str = html.bold(f"Raspberry Pi ID: {rp_id}\n\tStatus:\n")
    status_str = await get_rp_status(rp_id)
    conf_str = ""

    if rp_id not in mqtt_client.rp_configuration.keys():
        conf_str = html.bold("\tNo configuration stored")
    else:
        conf_result = get_configuration_str(int(rp_id))
        if conf_result:
            conf_str = html.bold("\tCurrent configuration:\n") + conf_result
            if "report_period" in mqtt_client.rp_configuration[int(rp_id)].keys():
                report_period = int(mqtt_client.rp_configuration[int(rp_id)]["report_period"]) / 100
    print(status_str)
    message_text = (header_str + status_str + conf_str)
    res = await message.answer(message_text, parse_mode=ParseMode.HTML)
    prev_time = time.time()
    while Conf.status_state:
        if time.time() - prev_time > report_period:
            print("Updating status")
            mqtt_client.client.publish("ice_runner/bot/usr_cmd/state", str(rp_id))
            mqtt_client.client.publish("ice_runner/bot/usr_cmd/stats", str(rp_id))
            await asyncio.sleep(0.3)
            status_str = await get_rp_status(rp_id)
            message_text = (header_str + status_str + conf_str)
            await res.edit_text(message_text, parse_mode=ParseMode.HTML)
            prev_time = time.time()

# @dp.message(Command(commands=["start", "запустить"], ignore_case=True))
# async def command_start_handler(message: Message) -> None:
#     """
#     This handler receives messages with `/start` command
#     """
#     print("TG:\tStart handler")
#     await message.answer(f"Hello, {html.bold(message.from_user.full_name)}!")
#     if not configuration:
#         print("TG:\tNo configuration stored")
#         await message.answer(f"No configuration stored. Send configuration with /conf command")
#     else:
#         print("TG:\tConfiguration stored")
#         await message.answer("Previous configuration: " + get_configuration_str(configuration))
#     await message.answer(f"Connected Raspberry Pi IDs:")
#     for id, state in mqtt_client.rp_states.items():
#         await message.answer(f"\t{id}: state - {state}")

@dp.message(Command(commands=["stop", "стоп"]))
async def command_stop_handler(message: Message) -> None:
    """
    This handler receives messages with `/stop` command
    """
    await message.answer(f"Stopping")
    mqtt_client.client.publish("ice_runner/bot/usr_cmd/stop", f"{rp_id}").wait_for_publish()
    rp_status = int(mqtt_client.rp_status[rp_id])
    while True:
        if rp_status != RPStates.RUNNING.value:
            break
        await message.answer(f"Raspberry Pi {rp_id} is stopping. Current state: {RPStates(rp_status).name}")
        await asyncio.sleep(1)
    await message.answer(f"Stopped")


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
    dp.include_router(form_router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())

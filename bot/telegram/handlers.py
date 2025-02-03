#!/usr/bin/env python3
# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import asyncio
import logging
import re
import sys
import os

from typing import Any, Dict, List, Tuple
from aiogram import Router, Dispatcher, types, F, html
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.strategy import FSMStrategy
from aiogram.types import (
    Message,
    ReplyKeyboardRemove,
    FSInputFile
)
from aiogram.fsm.storage.memory import MemoryStorage

from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message
import yaml

from mqtt.client import MqttClient
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from common.RPStates import RPFlags
import pprint
import time
from datetime import datetime

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
    "/cancel": "Отменить последнее действие/\nCancel any action\n",
    "/choose_rp": "Выберите ID обкатчика/\n Choose ID of the ICE runner\n",
    "/log": "Прислать логи блока ДВС/\nSend logs of the connected block\n",
    "/run": "Запускает автоматическую обкатку ДВС используя последние настроенные параметры/\nStart the automatic running using the last configuration\n",
    "/server": "Проверяет работу сервера./\n Check server status\n",
    "/show_all": "Показать все состояния блоков ДВС/\nShow all states of connected blocks\n",
    "/status": "Получить статус подключенных блоков ДВС и текущие настройки/\nGet the status of the connected blocks and current configuration\n",
    "/stop": "Остановить обкатку двигателей/\nStop the automatic running immediately\n",
    "/help": "Выдать список доступных команд/\nSend a list of available commands\n",
}

dp = Dispatcher(storage=MemoryStorage(), fsm_strategy=FSMStrategy.CHAT)
form_router = Router()
dp.include_router(form_router)

configuration: Dict[int, Dict[str, Any]] = {}
configuration_file_path: str = None

def get_configuration_from_file(path: str) -> None:
    global configuration_file_path
    global configuration
    configuration_file_path = path
    if not os.path.exists(configuration_file_path):
        return
    with open(configuration_file_path, "r") as file:
        configuration = yaml.safe_load(file)

def get_configuration_str(rp_id: int) -> str:
    if rp_id not in MqttClient.rp_configuration.keys():
        return "Нет настроек обкатки для обкатчика " + str(rp_id)
    conf = MqttClient.rp_configuration[int(rp_id)]
    conf_str = ""
    if conf:
        if pprint.isrecursive(conf):
            for rp_id, config in conf.items():
                conf_str += f"Настройки обкатчика {rp_id} :\n"
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
            return "\tОбкатчик не обновил свой статус\n", False

    await asyncio.sleep(0.5)
    status = MqttClient.rp_status[rp_id]
    rp_state = MqttClient.rp_states[rp_id]
    MqttClient.rp_status[rp_id] = None
    MqttClient.rp_states[rp_id] = None
    if rp_state is not None:
        status_str = "\t\tСтатус: " + rp_state.name + '\n'
        if status is None:
            status_str = "\tОбкатчик не шлет свой статус\n"
        else:   
            for name, value in list(status.items()):
                status_str += f"\t\t\t{name}: {value}\n"
    else:
        MqttClient.rp_status.pop(rp_id)
        MqttClient.rp_states.pop(rp_id)
        status_str = "\tОбкатчик молчит\n"

    last_status_update = time.time()
    data["last_status_update"] = last_status_update
    await state.update_data(data)
    update_time = datetime.fromtimestamp(last_status_update).strftime('%Y-%m-%d %H:%M:%S') + '\n'
    return status_str + "\n\tвремя обновления: " + update_time, True

async def show_options(message: types.Message, state: FSMContext) -> None:
    MqttClient.client.publish("ice_runner/bot/usr_cmd/who_alive")
    await asyncio.sleep(0.5)
    available_rps = list(MqttClient.rp_states.keys())
    if len(available_rps) == 0:
        await message.answer("Нет доступных обкатчиков")
        return
    kb = [[types.KeyboardButton(text=str(rp_id) + "\tStatus: " + MqttClient.rp_states[rp_id].name) for rp_id in available_rps]]
    keyboard = types.ReplyKeyboardMarkup(keyboard=kb)
    await message.reply("Выберите ID обкатчика", reply_markup=keyboard)
    await state.set_state(Conf.rp_id)

class Conf(StatesGroup):
    rp_id = State()
    conf_state = State()
    status_state = State()
    show_all_state = State()
    starting_state = State()

@form_router.message(Conf.conf_state)
async def process_configuration(message: types.Message, state: FSMContext):
    """Process configuration of the runner"""
    # The configuration is not implemented
    pass

@form_router.message(Command(commands=["choose_rp", "выбрать_ДВС"]))
async def choose_rp_id(message: types.Message, state: FSMContext) -> None:
    await state.set_state(Conf.rp_id)
    await show_options(message, state)

@form_router.message(Conf.rp_id)
async def rp_id_handler(message: types.Message, state: FSMContext) -> None:
    id = message.text.split(" ")[0]
    if not id.isdigit():
        if "/cancel" in message.text.casefold() or "cancel" in message.text.casefold():
            await cancel_handler(message, state)
        else:
            await message.reply("Пожалуйста, введите числовой ID обкатчика или отмените команду с помощью /cancel.")
        return

    rp_id_num = int(id)
    if rp_id_num not in MqttClient.rp_status.keys():
        await message.reply("Обкатчик с таким ID не найден")
        return
    await message.reply(f"ID выбранного обкатчика: {rp_id_num}")
    await state.clear()
    await state.set_data({"rp_id": rp_id_num})

# Commands handlers
@dp.message(Command(commands=["conf", "настроить_обкатку", "configure", "настройка"]))
async def command_conf_handler(message: types.Message, state: FSMContext):
    # The configuration is not implemented
    pass

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
        "Отменено.",
        reply_markup=ReplyKeyboardRemove(),
    )

@form_router.message(Command(commands=["run", "запустить"], ignore_case=True))
async def command_run_handler(message: Message, state: FSMContext) -> None:
    """
    This handler receives messages with `/run` command
    """
    if "rp_id" not in (await state.get_data()).keys():
        await show_options(message, state)
        return
    rp_id = (await state.get_data())["rp_id"]
    rp_state = MqttClient.rp_states[rp_id]
    await message.answer(f"ID обкатчика: {rp_id}\nСтатус обкатчика: {rp_state.name}\n")
    await message.answer("Настройки обкатки:" + get_configuration_str(rp_id))
    print(rp_state)
    await state.set_state(Conf.starting_state)
    if rp_state == "RUNNING" or rp_state == "STARTING":
        await message.answer(f"Обкатка уже запущена")
        return
    await message.answer(f"Отправьте /cancel или /отмена чтобы отменить запуск обкатки. После запуска отправьте /stop или /стоп чтобы остановить ее")
    i = 0
    logging.getLogger(__name__).info(f"received CMD START from user {message.from_user.username}")
    while i < 5 and ((await state.get_state()) == Conf.starting_state):
        await message.answer(f"Запуск через {5-i}")
        i += 1
        await asyncio.sleep(1)

    if ((await state.get_state()) != Conf.starting_state):
        logging.getLogger(__name__).info(f"CMD START aborted by user")
        return

    for i in range(5):
        if (await state.get_state()) != Conf.starting_state:
            return
        message.answer(f"Пробуем еще раз")
        MqttClient.client.publish("ice_runner/bot/usr_cmd/start", str(rp_id))
        await asyncio.sleep(1)
        rp_state = MqttClient.rp_states[rp_id].name
        if rp_state == "STARTING":
            await message.answer(f"Запущено")
            break
        else:
            await message.answer(f"Ошибка\n\t{rp_state}")
    logging.getLogger(__name__).info(f"CMD START send to Raspberry Pi {rp_id}")

@dp.message(Command(commands=["help", "помощь"]))
async def command_help_handler(message: Message) -> None:
    """
    This handler receives messages with `/help` command
    """
    help_str = ''
    for command, description in commands_discription.items():
        help_str += f"<b>- {command}</b>:\n\t{description}\n"
    await message.answer(
        "Список команд:\n" + help_str, parse_mode=ParseMode.HTML)

@dp.message(Command(commands=["show_all", "показать_все"]))
async def command_show_all_handler(message: Message, state: FSMContext) -> None:
    """
    This handler receives messages with `/show_all` command
    """
    MqttClient.client.publish("ice_runner/bot/usr_cmd/who_alive")
    await state.set_state(Conf.show_all_state)
    await asyncio.sleep(1)
    messages: List[Dict[str, Any]] = []
    message_text = ""
    connected_nodes = MqttClient.rp_status.keys()
    await message.answer(f"Количество подключенных обкатчиков: {len(connected_nodes)}")
    if len(connected_nodes) == 0:
        return

    for rp_id in list(MqttClient.rp_states.keys()):
        logging.info(f"Sending status cmd for {rp_id}")
        MqttClient.client.publish(f"ice_runner/bot/usr_cmd/command/status", str(rp_id))
        await asyncio.sleep(0.5)
        header_str = html.bold(f"ID обкатчика: {rp_id}\n\tСтатус:\n" )
        report_period = 10
        data = await state.get_data()
        MqttClient.client.publish(f"ice_runner/bot/usr_cmd/command/config", str(rp_id))
        await asyncio.sleep(0.5)
        logging.info(f"Config {MqttClient.rp_configuration}")
        if MqttClient.rp_configuration[int(rp_id)] is None:
            conf_str = html.bold("\tНет настроек обкатки\n")
        else:
            report_period = int(MqttClient.rp_configuration[int(rp_id)]["report_period"])
            conf_str = html.bold("\tНастройки обкатки:\n") + get_configuration_str(rp_id)
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
        await show_options(message, state)
        return
    rp_id = data["rp_id"]

    MqttClient.client.publish("ice_runner/bot/usr_cmd/config", str(rp_id))
    MqttClient.client.publish("ice_runner/bot/usr_cmd/state", str(rp_id))
    MqttClient.client.publish("ice_runner/bot/usr_cmd/status", str(rp_id))
    await asyncio.sleep(0.5)

    header_str = html.bold(f"ICE Runner ID: {rp_id}\n\tСтатус:\n")

    if rp_id not in MqttClient.rp_configuration.keys():
        conf_str = html.bold("\tНет настроек обкатки")
    else:
        conf_result = get_configuration_str(int(rp_id))
        if conf_result:
            conf_str = html.bold("\tНастройки обкатки\n") + conf_result
        if "report_period" not in data.keys():
            if "report_period" in MqttClient.rp_configuration[int(rp_id)].keys():
                report_period = int(MqttClient.rp_configuration[int(rp_id)]["report_period"])
            else:
                report_period = 10
            data["report_period"] = report_period
    await state.set_data(data)
    status_str, is_updated = await get_rp_status(rp_id, state)

    message_text = (header_str + status_str + conf_str)
    res = await message.answer(message_text, parse_mode=ParseMode.HTML)
    await asyncio.sleep(0.5)
    while ((await state.get_state()) == Conf.status_state):
        logging.info("Updating status ", await state.get_data())
        status_str, is_updated = await get_rp_status(rp_id, state)
        if not is_updated:
            continue
        message_text = (header_str + status_str + conf_str)
        response = await res.edit_text(message_text, parse_mode=ParseMode.HTML)
        await asyncio.sleep(0.5)

@form_router.message(Command(commands=["log", "лог"]))
async def command_log_handler(message: Message, state: FSMContext) -> None:
    """
    This handler receives messages with `/log` command
    """
    if "rp_id" not in (await state.get_data()).keys():
        await show_options(message, state)
        return
    rp_id = (await state.get_data())["rp_id"]
    logging.getLogger(__name__).info(f"Getting logs for {rp_id}")
    MqttClient.client.publish("ice_runner/bot/usr_cmd/log", str(rp_id))
    await asyncio.sleep(0.3)
    logging.info(f"Data for {MqttClient.rp_logs}")
    if rp_id in MqttClient.rp_logs.keys():
        log_files = MqttClient.rp_logs[rp_id]
        for name, log_file in log_files.items():
            logging.info(f"Sending log {name}")
            try:
                log = FSInputFile(log_file)
                await message.answer_document(log, caption=name)
            except Exception as e:
                await message.answer(f"Ошибка при отправке лога {name}: {e}")
                logging.getLogger(__name__).error(f"Error sending log {name}: {e}")
    else:
        await message.answer("Лог не найден")

@form_router.message(Command(commands=["stop", "стоп"]))
async def command_stop_handler(message: Message, state: FSMContext) -> None:
    """
    This handler receives messages with `/stop` command
    """
    await message.answer(f"Отправляем команду остановки")
    if "rp_id" not in (await state.get_data()).keys():
        await show_options(message, state)
        return
    rp_id = (await state.get_data())["rp_id"]
    MqttClient.client.publish("ice_runner/bot/usr_cmd/stop", f"{rp_id}")
    MqttClient.client.publish("ice_runner/bot/usr_cmd/stop", f"{rp_id}")
    rp_status = MqttClient.rp_states[rp_id]
    while True:
        if rp_status != RPFlags.RUNNING:
            break
        await message.answer(f"Команда отправленна на обкатчик {rp_id}. Текущий статус: {rp_status.name}")
        MqttClient.client.publish("ice_runner/bot/usr_cmd/stop", f"{rp_id}")
        await asyncio.sleep(1)
    await message.answer(f"Остановлено")

@form_router.message(Command(commands=["server", "сервер"]))
async def command_server(message: Message, state: FSMContext) -> None:
    """
    This handler receives messages with `/server` command
    """
    await message.answer("Проверяем работу сервера")
    MqttClient.client.publish("ice_runner/bot/usr_cmd/server", "server")
    await asyncio.sleep(1)
    if MqttClient.server_connected:
        await message.answer("Сервер подключен")
    else:
        await message.answer("Сервер не подключен")
    MqttClient.server_connected = False

@form_router.message(F.text.lower().not_in(commands_discription.keys()))
async def unknown_message(msg: types.Message, state: FSMContext):
    message_text = 'Я не знаю, что с этим делать \nЯ просто напомню, что есть команда /help'
    logging.getLogger(__name__).warning(msg.text, await state.get_state())
    await msg.reply(message_text, parse_mode=ParseMode.HTML)

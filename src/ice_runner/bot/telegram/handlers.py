"""The module defines handlers for the Telegram Bot messages"""

# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import asyncio
from copy import copy
from dataclasses import dataclass
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Tuple
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import Router, Dispatcher, types, F, html
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.strategy import FSMStrategy
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.methods.send_message import SendMessage
from aiogram.types import (
    Message,
    ReplyKeyboardRemove,
)

from bot.mqtt.client import MqttClient
from bot.telegram.filters import ChatIdFilter
from common.algorithms import get_type_from_str, is_float
from common.RunnerState import RunnerState

COMMANDS_DESCRIPTION : Dict[str, str] = {
    "/cancel":      "Отменить последнее действие.",
    "/choose_rp":   "Выбрать ID обкатчика.",
    "/config":      "Изменить настройки.",
    "/log":         "Прислать логи.",
    "/run":         "Запустить обкатку.",
    "/server":      "Проверить работу сервера.",
    "/show_all":    "Показать все состояния.",
    "/status":      "Получить статус и настройки.",
    "/stop":        "Остановить обкатку.",
    "/help":        "Получить список команд.",
}
MAX_COMMAND_LENGTH = max(len(command) for command in COMMANDS_DESCRIPTION)
WAIT_BEFORE_RUN_TIME = 5
RUNNER_ID = None
dp = Dispatcher(storage=MemoryStorage(), fsm_strategy=FSMStrategy.CHAT)
form_router = Router()
dp.include_router(form_router)
configuration_file_path: str = None

@dataclass
class BotState(StatesGroup):
    """The class is used to define states of the bot"""
    status_state = State()
    show_all_state = State()
    starting_state = State()
    config_change = State()
    param_change = State()

################################################################################
# Handlers
################################################################################

@form_router.message(Command(commands=["stop", "стоп"]), ChatIdFilter())
async def command_stop_handler(message: Message, state: FSMContext) -> None:
    """
    This handler receives messages with `/stop` command
    """
    await message.answer(f"Отправляем команду остановки")
    if RUNNER_ID is None:
        await show_options(message)
        return
    MqttClient.client.publish("ice_runner/bot/usr_cmd/stop", str(RUNNER_ID))
    MqttClient.client.publish("ice_runner/bot/usr_cmd/stop", str(RUNNER_ID))
    while True:
        rp_status = MqttClient.rp_states[RUNNER_ID]
        if rp_status != RunnerState.RUNNING:
            break
        await message.answer(
            f"Команда отправленна на обкатчик {RUNNER_ID}.\nТекущий статус: {rp_status.name}")
        MqttClient.client.publish("ice_runner/bot/usr_cmd/stop", str(RUNNER_ID))
        await asyncio.sleep(1)
    await message.answer(f"Остановлено")

@form_router.message(Command(commands=["run", "запустить"], ignore_case=True), ChatIdFilter())
async def command_run_handler(message: Message, state: FSMContext) -> None:
    """
    This handler receives messages with `/run` command
    """
    if RUNNER_ID is None:
        await show_options(message)
        return
    runner_id = RUNNER_ID
    rp_state = MqttClient.rp_states[runner_id].name
    if rp_state in ('RUNNING', 'STARTING'):
        await message.answer("Ошибка\nОбкатка уже запущена, отправьте /stop или /стоп чтобы остановить ее")
        return
    if rp_state == "NOT_CONNECTED":
        await message.answer("Ошибка\nОбкатчик не подключен")
        return
    info_mes: str = "Настройки обкатки:\n" + (await get_configuration_str(runner_id) + "\n")
    await state.set_state(BotState.starting_state)
    info_mes += "Отправьте /cancel или /отмена чтобы отменить запуск обкатки.\
                         После запуска отправьте /stop или /стоп чтобы остановить ее"
    await message.answer(info_mes)
    logging.info("received CMD START from user %s", message.from_user.username)
    counter_message: str = f"Запуск через {WAIT_BEFORE_RUN_TIME}\n"
    res: SendMessage = await message.answer(counter_message, parse_mode=ParseMode.MARKDOWN)

    for i in range(1, WAIT_BEFORE_RUN_TIME):
        await asyncio.sleep(1)
        if (await state.get_state()) != BotState.starting_state:
            logging.info("CMD START aborted by user")
            return
        counter_message = f"Запуск через {WAIT_BEFORE_RUN_TIME-i}\n"
        await res.edit_text(counter_message, parse_mode=ParseMode.MARKDOWN)

    if (await state.get_state()) != BotState.starting_state:
        logging.info("CMD START aborted by user")
        return

    MqttClient.publish_start(runner_id)
    await asyncio.sleep(1)
    await state.set_state()

    if runner_id not in MqttClient.rp_states:
        await res.edit_text(counter_message+"Ошибка: Raspberry Pi отключился")
        MqttClient.publish_stop(runner_id)
        return
    rp_state = MqttClient.rp_states[runner_id].name
    if rp_state == "STARTING":
        await res.edit_text(counter_message+"Запущено")
        return
    if rp_state == "RUNNING":
        await res.edit_text(counter_message+"Ошибка: двигатель завелся слишком быстро, останавливаем его")
    elif rp_state == "FAULT":
        await res.edit_text(counter_message+"Фатальная ошибка, останавливаем двигатель")
    elif rp_state == "NOT_CONNECTED":
        await res.edit_text(counter_message+"Ошибка: Двигатель отключился")
    elif rp_state == "STOPPED":
        await res.edit_text(counter_message+"Ошибка: Двигатель не запустился")
    else:
        await res.edit_text(counter_message+"Ошибка: неизвестное состояние")
    MqttClient.publish_stop(runner_id)
    await res.edit_text(counter_message+f"Ошибка: {rp_state}")

@form_router.message(Command(commands=["status", "статус"]), ChatIdFilter())
async def command_status_handler(message: Message, state: FSMContext) -> None:
    """
    This handler receives messages with `/status` command
    """
    await state.set_state(BotState.status_state)
    data = await state.get_data()
    if RUNNER_ID is None:
        await show_options(message)
        return
    runner_id = RUNNER_ID
    MqttClient.client.publish("ice_runner/bot/usr_cmd/config", str(runner_id))
    MqttClient.client.publish("ice_runner/bot/usr_cmd/state", str(runner_id))
    MqttClient.client.publish("ice_runner/bot/usr_cmd/status", str(runner_id))
    await asyncio.sleep(0.5)
    upd_state = await set_report_period(runner_id, state)

    status_str, _ = await get_rp_status(runner_id, upd_state)

    last_status_update = time.time()
    data["last_status_update"] = last_status_update
    data = await upd_state.get_data()
    await state.set_data(data)

    res: SendMessage = await message.answer(status_str, parse_mode=ParseMode.MARKDOWN)
    report_period = data["report_period"]
    await asyncio.sleep(report_period)

    while ((await state.get_state()) == BotState.status_state):
        logging.info("Updating status")
        MqttClient.client.publish("ice_runner/bot/usr_cmd/state", str(runner_id))
        MqttClient.client.publish("ice_runner/bot/usr_cmd/status", str(runner_id))
        status_str, _ = await get_rp_status(runner_id, state)
        last_status_update = time.time()
        data["last_status_update"] = last_status_update
        await state.set_data(data)
        await res.edit_text(status_str, parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(report_period)

@form_router.message(Command(commands=["config", "изменить_настройки"]), ChatIdFilter())
async def change_config(message: types.Message, state: FSMContext) -> None:
    """The function handles the command to change the configuration"""
    if RUNNER_ID is None:
        await show_options(message)
        return
    runner_id = RUNNER_ID
    logging.debug("Send conf command to rpi %d", runner_id)
    MqttClient.publish_config_request(runner_id)
    await asyncio.sleep(0.5)
    rp_state = MqttClient.rp_states[runner_id].name
    await message.answer("Настройки обкатки:\n" + (await get_configuration_str(runner_id)))
    rp_config = MqttClient.rp_configuration[runner_id]
    if len(rp_config) == 0:
        await message.answer("Ошибка, нет настроек обкатки")
        logging.error("No configuration for %d", runner_id)
        return
    help_message = "Отправьте новые настройки в формате имя: значение.\n"
    help_message += "Начните сообщение с '/'.\nНапример:\n"
    help_message += "\n/rpm: 4000\ntime: 100\ngas_throttle: 0\n"
    help_message += "Чтобы получить подсказку по командам, напишите /tip"

    await message.answer(help_message)
    await state.set_state(BotState.config_change)

@form_router.message(Command(commands=["tip"]), ChatIdFilter(), BotState.config_change)
async def config_tip_handler(message: Message, state: FSMContext) -> None:
    """The function handles tip message with configuration change"""
    data = await state.get_data()
    runner_id = RUNNER_ID
    full_conf = await get_full_configuration(runner_id)
    base_params = [key for key, value in full_conf.items() if 'base' in value["usage"]]
    other_params = [key for key, value in full_conf.items() if 'other' in value["usage"]]
    flag_params = [key for key, value in full_conf.items() if 'flag' in value["usage"]]
    string = html.bold("Базовые параметры:\n")
    for param_name in base_params:
        param_data = full_conf[param_name]
        string += f"\n{param_name}:\n"
        for name, value in param_data.items():
            string += f"\t{name}: {value}\n"
    await message.answer(string)
    string = html.bold("Другие параметры:\n")
    for param_name in other_params:
        param_data = full_conf[param_name]
        string += f"\n{param_name}:\n"
        for name, value in param_data.items():
            string += f"\t{name}: {value}\n"
    await message.answer(string)
    string = html.bold("Флаги:\n")
    for param_name in flag_params:
        param_data = full_conf[param_name]
        string += f"\n{param_name}:\n"
        for name, value in param_data.items():
            string += f"\t{name}: {value}\n"
    await message.answer(string)

@form_router.message(F.text.lower().not_in(COMMANDS_DESCRIPTION.keys()), BotState.config_change)
async def config_change_handler(message: Message, state: FSMContext) -> None:
    """The function handles messages with configuration change"""
    await state.set_state()
    data = await state.get_data()
    runner_id = RUNNER_ID
    text = copy(message.text)
    if ("@" in text ) or ( "/" in text):
        text = text.split("@")[0].replace("/", "").replace(" ", "")
    params_dict ={}
    for params in text.split("\n"):
        if not params:
            message.reply(f"Параметры не указаны")
            logging.warning("Param change failed, %s no params", params)
            continue
        if ":" not in params:
            logging.warning("Param change failed, wrond msg format %s", params)
            await message.reply("Неверный формат команды")
            return
        param_name, param_value = params.split(":")
        logging.info("Param change %s %s", param_name, param_value)
        params_dict[param_name] = param_value

    for param_name, param_value in params_dict.items():
        if not is_float(param_value):
            logging.warning("Wrong param value, %s is not a digit", param_value)
            await message.reply(
                f"Неверное значение параметра {param_name}: {param_value} не является числом")
            return
    full_conf = await get_full_configuration(runner_id)

    for param_name, param_value_str in params_dict.items():
        type_of_param = get_type_from_str(full_conf[param_name]["type"])
        param_value = type_of_param(param_value_str)
        params_dict[param_name] = param_value

    res: Dict[str, bool] = check_parameters_borders(params_dict, full_conf)
    for param_name, param_flag in res.items():
        if not param_flag:
            logging.warning("Wrong param value %s", param_name)
            await message.reply(
                f"Неверное значение параметра {param_name}:" +
                f"min {full_conf[param_name]['min']}, max {full_conf[param_name]['max']}")
            return

    reply_text = ""
    for param_name, param_value_str in params_dict.items():
        MqttClient.client.publish(
            f"ice_runner/bot/usr_cmd/{runner_id}/change_config/{param_name}", param_value_str)
        reply_text += f"Новое значение параметра {param_name} отправлено {param_value_str}\n"
    reply_message: Message = await message.answer(reply_text)
    await asyncio.sleep(0.5)
    MqttClient.publish_config_request(runner_id)
    await asyncio.sleep(2)
    if full_conf is None:
        reply_message.edit_text(reply_text + "Ошибка, нет настроек обкатки")
        return
    for param_name, param_value in params_dict.items():
        type_of_param = get_type_from_str(full_conf[param_name]["type"])
        n_success = 0
        if MqttClient.rp_configuration[runner_id][param_name] == type_of_param(param_value):
            reply_text += f"Параметр {param_name} установлен в нужное значение\n"
            n_success += 1
        else:
            reply_text += f"Параметр {param_name} не обновлен\n"
        reply_message.edit_text(reply_text + "Ошибка, нет настроек обкатки")
    await message.answer(f"{n_success} параметров успешно обновлено\n" +
                                (await get_configuration_str(runner_id)))

@form_router.message(Command(commands=["log", "лог"]), ChatIdFilter())
async def command_log_handler(message: Message, state: FSMContext) -> None:
    """
    This handler receives messages with `/log` command
    """
    if RUNNER_ID is None:
        await show_options(message)
        return
    runner_id = RUNNER_ID
    logging.info("Getting logs for %d", runner_id)
    MqttClient.client.publish("ice_runner/bot/usr_cmd/log", str(runner_id))
    await message.answer("Пожалуйста, подождите")

@form_router.message(Command(commands=["cancel", "отмена"]), ChatIdFilter())
async def cancel_handler(message: Message, state: FSMContext) -> None:
    """
    Allow user to cancel any action
    """
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Нет активных действий для отмены.",
                             reply_markup=ReplyKeyboardRemove())
        return
    logging.info("Cancelling state %r", current_state)
    await state.clear()
    await message.answer(
        "Отменено.",
        reply_markup=ReplyKeyboardRemove(),
    )

@dp.message(Command(commands=["help", "помощь"]))
async def command_help_handler(message: Message) -> None:
    """
    This handler receives messages with `/help` command
    """
    help_str = ''
    for command, description in COMMANDS_DESCRIPTION.items():
        # For some reasons we need 2 spaces in telegram to allign the command name
        padding_spaces = "  " * (MAX_COMMAND_LENGTH - len(command))
        help_str += f"<b>- {command}</b>{padding_spaces}: {description}\n"
    await message.answer(
        "Список команд:\n" + help_str, parse_mode=ParseMode.HTML)

@form_router.message(Command(commands=["server", "сервер"]), ChatIdFilter())
async def command_server(message: Message) -> None:
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

@form_router.message(F.text.lower().not_in(COMMANDS_DESCRIPTION.keys()), ChatIdFilter())
async def unknown_message(msg: types.Message):
    """The function handles unknown messages"""
    message_text = 'Я не знаю, что с этим делать \nЯ просто напомню, что есть команда /help'
    logging.warning("Unknown message send %s", msg.text)
    await msg.reply(message_text, parse_mode=ParseMode.HTML)

@form_router.message(ChatIdFilter(invert=True))
async def unknown_user(msg: types.Message):
    """The function handles messages from unknown chats"""
    message_text = 'Я вас не знаю, уходите'
    logging.warning("Unknown user send %s", msg.text)
    await msg.reply(message_text, parse_mode=ParseMode.HTML)

@form_router.message(Command(commands=["choose_rp", "выбрать_ДВС"]), ChatIdFilter())
async def choose_rp_id(message: types.Message) -> None:
    """The function handles the command to choose RPi"""
    await show_options(message)

@dp.message(Command(commands=["show_all", "показать_все"]), ChatIdFilter())
async def command_show_all_handler(message: Message, state: FSMContext) -> None:
    """
    This handler receives messages with `/show_all` command
    """
    MqttClient.publish_who_alive()
    await state.set_state(BotState.show_all_state)
    await asyncio.sleep(1)
    messages: List[Dict[str, Any]] = []
    message_text = ""
    connected_nodes = MqttClient.rp_status.keys()
    await message.answer(f"Количество подключенных обкатчиков: {len(connected_nodes)}")
    if len(connected_nodes) == 0:
        return

    for runner_id in list(MqttClient.rp_states.keys()):
        conf_str = ""
        logging.info("Sending status cmd for %d", runner_id)
        MqttClient.client.publish(f"ice_runner/bot/usr_cmd/status", str(runner_id))
        await asyncio.sleep(0.5)
        header_str = html.bold(f"ID обкатчика: {runner_id}\n\tСтатус:" )
        data = await state.get_data()
        logging.info("Send conf command to rpi %d", runner_id)
        MqttClient.client.publish("ice_runner/bot/usr_cmd/config", str(runner_id))
        await asyncio.sleep(1)

        logging.info("Config %s", MqttClient.rp_configuration)
        if MqttClient.rp_configuration[int(runner_id)] is None:
            conf_str = html.bold("\tНет настроек обкатки\n")
        else:
            conf_str = html.bold("\tНастройки обкатки:\n") +\
                                        (await get_configuration_str(runner_id))
        await state.set_data(data)
        status_str, _ = await get_rp_status(int(runner_id), state)
        message_text += (header_str + status_str + conf_str)

        messages.append({"runner_id": runner_id,
                         "header": header_str,
                         "status": status_str,
                         "conf": conf_str})
        await asyncio.sleep(0.3)
    await message.answer(message_text, parse_mode=ParseMode.HTML)
    await state.set_data({})

@form_router.callback_query(F.data.isdigit())
async def choose_runner_id_callback(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    """The function handles callback query from RPi id selection buttons"""
    runner_id_num = int(callback_query.data)
    await callback_query.message.answer(f"ID выбранного обкатчика: {runner_id_num}")
    RUNNER_ID = runner_id_num

################################################################################
# Helper functions
################################################################################

async def set_report_period(runner_id: int, state: FSMContext):
    """The function sets the report period for the Raspberry Pi,
        returns the report period string and the state of the info was is updated"""
    data = await state.get_data()
    if "report_period" in data.keys():
        return
    report_period = 10
    if runner_id in MqttClient.rp_configuration:
        if "report_period" not in data:
            if "report_period" in MqttClient.rp_configuration[int(runner_id)]:
                report_period = int(MqttClient.rp_configuration[int(runner_id)]["report_period"])
    data["report_period"] = report_period
    await state.set_data(data)
    return state

async def get_configuration_str(runner_id: int) -> str:
    """The function returns the configuration string for the specified RP id
        stored in MQTT client"""
    MqttClient.publish_config_request(runner_id)
    await asyncio.sleep(0.5)
    if runner_id not in MqttClient.rp_configuration:
        return "Нет настроек обкатки для обкатчика " + str(runner_id)
    conf = MqttClient.rp_configuration[int(runner_id)]
    conf_str = ""
    if conf:
        for name, value in conf.items():
            conf_str += f"\t{name}: {value}\n"
    return conf_str

async def get_full_configuration(runner_id: int) -> Dict[str, Any]:
    """The function returns the full configuration dictionary for the specified RPi
        stored in MQTT client"""
    i = 0
    while runner_id not in MqttClient.runner_full_configuration:
        MqttClient.publish_full_config_request(runner_id)
        await asyncio.sleep(2)
        i += 1
        if i > 5:
            logging.error("No configuration for %d", runner_id)
            return None
    return MqttClient.runner_full_configuration[runner_id]

async def get_rp_status(runner_id: int, state: FSMContext) -> Tuple[str, bool]:
    """The function sets the status of the Raspberry Pi,
        returns the status string and the state of the info was is updated"""
    await asyncio.sleep(0.4)
    data = await state.get_data()

    await asyncio.sleep(0.5)
    status = MqttClient.rp_status[runner_id]
    rp_state = MqttClient.rp_states[runner_id]
    MqttClient.rp_status[runner_id] = None
    MqttClient.rp_states[runner_id] = None
    status_str = ""
    if rp_state is None:
        MqttClient.rp_status.pop(runner_id)
        MqttClient.rp_states.pop(runner_id)
        status_str = "\tОбкатчик молчит\n"
    else:
        if status is None:
            status_str = "\tОбкатчик не шлет свой статус\n"
        else:
            for name, value in status.items():
                status_str += f"{name}:\t{value}\n"
    last_status_update = time.time()
    data["last_status_update"] = last_status_update
    await state.update_data(data)
    update_time = datetime.fromtimestamp(last_status_update).strftime('%Y-%m-%d %H:%M:%S') + '\n'
    return status_str + "\nвремя обновления: " + update_time, True

async def show_options(message: types.Message) -> None:
    """The function creates set of buttons of available RPis"""
    MqttClient.publish_who_alive()
    await asyncio.sleep(0.5)
    available_rps = list(MqttClient.rp_states.keys())
    if len(available_rps) == 0:
        await message.answer("Нет доступных обкатчиков")
        return
    builder = InlineKeyboardBuilder()

    for runner_id in available_rps:
        builder.add(types.InlineKeyboardButton(
            text= f"{runner_id}\tStatus: { MqttClient.rp_states[runner_id].name}",
            callback_data=str(runner_id))
        )
    await message.answer(
        "Нажмите на кнопку, чтобы выбрать ID обкатчика",
        reply_markup=builder.as_markup()
    )

def check_parameters_borders(params: Dict[str, Any],
                                   full_conf: Dict[str, Any]) -> Dict[str, bool]:
    """The function checks if all parameters are set correctly"""
    check_dict = {}
    for param_name, param_value in params.items():
        min_value = full_conf[param_name]["min"]
        max_value = full_conf[param_name]["max"]
        if min_value <= param_value <= max_value:
            check_dict[param_name] = True
        else:
            check_dict[param_name] = False
    return check_dict

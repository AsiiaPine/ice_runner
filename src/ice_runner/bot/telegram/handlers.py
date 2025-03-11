"""The module defines handlers for the Telegram Bot messages"""

# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import asyncio
from copy import copy
from dataclasses import dataclass
import logging
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
from aiogram.types import (
    Message,
    ReplyKeyboardRemove,
)

from bot.mqtt.client import MqttClient
from bot.telegram.filters import ChatIdFilter
from common.algorithms import get_type_from_str, is_float, safe_literal_eval
from common.RunnerState import RunnerState

commands_discription : Dict[str, str] = {
    "/cancel":      "Отменить последнее действие/\nCancel any action\n",
    "/choose_rp":   "Выбрать ID обкатчика/\n Choose ID of the ICE runner\n",
    "/config":      "Изменить настройки блока ДВС/\n\
Change the configuration of the connected block\n",
    "/log":         "Прислать логи блока ДВС/\nSend logs of the connected block\n",
    "/run":         "Запустить автоматическую обкатку ДВС/\n\
Start the automatic running using the last configuration\n",
    "/server":      "Проверить работу сервера./\n Check server status\n",
    "/show_all":    "Показать все состояния блоков ДВС/\nShow all states of connected blocks\n",
    "/status":      "Получить статус подключенных блоков ДВС и текущие настройки/\n\
Get the status of the connected blocks and current configuration\n",
    "/stop":        "Остановить обкатку двигателей/\nStop the automatic running immediately\n",
    "/help":        "Выдать список доступных команд/\nSend a list of available commands\n",
}

dp = Dispatcher(storage=MemoryStorage(), fsm_strategy=FSMStrategy.CHAT)
form_router = Router()
dp.include_router(form_router)
configuration_file_path: str = None

async def get_configuration_str(rp_id: int) -> str:
    """The function returns the configuration string for the specified RP id
        stored in MQTT client"""
    MqttClient.publish_config_request(rp_id)
    await asyncio.sleep(0.5)
    if rp_id not in MqttClient.rp_configuration:
        return "Нет настроек обкатки для обкатчика " + str(rp_id)
    conf = MqttClient.rp_configuration[int(rp_id)]
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

def get_emoji(state: RunnerState) -> str:
    """The function returns the emoji for the specified state"""
    if state == RunnerState.NOT_CONNECTED:
        return "🚫"
    if state == RunnerState.RUNNING:
        return "🚀"
    if state == RunnerState.STARTING:
        return "🔵"
    if state == RunnerState.STOPPED:
        return "🛑"
    if state == RunnerState.STOPPING:
        return "🚩"
    if state == RunnerState.FAULT:
        return "⁉"


async def get_rp_status(rp_id: int, state: FSMContext) -> Tuple[Dict[str, Any], bool]:
    """The function sets the status of the Raspberry Pi,
        returns the status string and the state of the info was is updated"""
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
        status_str = "\t\tСтатус: " + rp_state.name + get_emoji(rp_state) + '\n'
        if status is None:
            status_str = "\tОбкатчик не шлет свой статус\n"
        else:
            for name, value in status.items():
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

async def show_options(message: types.Message) -> None:
    """The function creates set of buttons of available RPis"""
    MqttClient.publish_who_alive()
    await asyncio.sleep(0.5)
    available_rps = list(MqttClient.rp_states.keys())
    if len(available_rps) == 0:
        await message.answer("Нет доступных обкатчиков")
        return
    builder = InlineKeyboardBuilder()

    for rp_id in available_rps:
        builder.add(types.InlineKeyboardButton(
            text= f"{rp_id}\tStatus: { MqttClient.rp_states[rp_id].name}",
            callback_data=str(rp_id))
        )
    await message.answer(
        "Нажмите на кнопку, чтобы выбрать ID обкатчика",
        reply_markup=builder.as_markup()
    )

@dataclass
class BotState(StatesGroup):
    """The class is used to define states of the bot"""
    status_state = State()
    show_all_state = State()
    starting_state = State()
    config_change = State()
    param_change = State()

@form_router.message(Command(commands=["choose_rp", "выбрать_ДВС"]), ChatIdFilter())
async def choose_rp_id(message: types.Message) -> None:
    """The function handles the command to choose RPi"""
    await show_options(message)

@form_router.callback_query(F.data.isdigit())
async def choose_rp_id_callback(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    """The function handles callback query from RPi id selection buttons"""
    rp_id_num = int(callback_query.data)
    await callback_query.message.answer(f"ID выбранного обкатчика: {rp_id_num}")
    await state.set_data({"rp_id": rp_id_num})

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

@form_router.message(Command(commands=["config", "изменить_настройки"]), ChatIdFilter())
async def change_config(message: types.Message, state: FSMContext) -> None:
    """The function handles the command to change the configuration"""
    if "rp_id" not in (await state.get_data()):
        await show_options(message)
        return
    rp_id = (await state.get_data())["rp_id"]
    logging.debug("Send conf command to rpi %d", rp_id)
    MqttClient.publish_config_request(rp_id)
    await asyncio.sleep(0.5)
    rp_state = MqttClient.rp_states[rp_id].name
    await message.answer(f"ID обкатчика: {rp_id}\nСтатус обкатчика: {rp_state}\n")
    await message.answer("Настройки обкатки:\n" + (await get_configuration_str(rp_id)))
    rp_config = MqttClient.rp_configuration[rp_id]
    if len(rp_config) == 0:
        await message.answer("Ошибка, нет настроек обкатки")
        logging.error("No configuration for %d", rp_id)
        return

    await message.answer("Отправьте новые настройки в формате имя: значение. Начните сообщение с '/'. Например:")
    await message.answer("/rpm: 4000\ntime: 100\ngas_throttle: 0")
    await message.answer("Чтобы получить подсказку по командам, напишите /tip")
    await state.set_state(BotState.config_change)

@form_router.message(Command(commands=["tip"]), ChatIdFilter(), BotState.config_change)
async def config_tip_handler(message: Message, state: FSMContext) -> None:
    """The function handles tip message with configuration change"""
    data = await state.get_data()
    runner_id = data["rp_id"]
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

@form_router.message(BotState.config_change)
async def config_change_handler(message: Message, state: FSMContext) -> None:
    """The function handles messages with configuration change"""
    data = await state.get_data()
    runner_id = data["rp_id"]
    text = copy(message.text)
    if ("@" in text ) or ( "/" in text):
        text = text.split("@")[0].replace("/", "")
    params_dict ={}
    for params in text.split("\n"):
        if not params:
            logging.warning("Param change failed, %s no params", params)
            continue
        if ":" not in params:
            logging.warning("Param change failed, wrond msg format %s", params)
            await message.answer("Неверный формат команды")
            return
        param_name, param_value = params.split(":")
        logging.info("Param change %s %s", param_name, param_value)
        params_dict[param_name] = param_value

    for param_name, param_value in params_dict.items():
        if not is_float(param_value):
            logging.warning("Wrong param value, %s is not a digit", param_value)
            await message.answer(
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
            await message.answer(
                f"Неверное значение параметра {param_name}:\
min {full_conf[param_name]['min']}, max {full_conf[param_name]['max']}")
            return

    for param_name, param_value_str in params_dict.items():
        MqttClient.client.publish(
            f"ice_runner/bot/usr_cmd/{runner_id}/change_config/{param_name}", param_value_str)
        await message.answer(f"Новое значение параметра {param_name} отправлено {param_value_str}")
    await asyncio.sleep(0.5)
    MqttClient.publish_config_request(runner_id)
    await asyncio.sleep(2)
    if full_conf is None:
        await message.answer("Ошибка, нет настроек обкатки")
        return
    for param_name, param_value in params_dict.items():
        type_of_param = get_type_from_str(full_conf[param_name]["type"])
        if MqttClient.rp_configuration[runner_id][param_name] == type_of_param(param_value):
            await message.answer(f"Параметр {param_name} установлен в нужное значение")
        else:
            await message.answer(f"Параметр {param_name} не установлен")
    await message.answer("Конфигурация успешно изменена\n" +
                                (await get_configuration_str(runner_id)))
    await state.set_state()

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

@form_router.message(Command(commands=["run", "запустить"], ignore_case=True), ChatIdFilter())
async def command_run_handler(message: Message, state: FSMContext) -> None:
    """
    This handler receives messages with `/run` command
    """
    if "rp_id" not in (await state.get_data()):
        await show_options(message)
        return
    rp_id = (await state.get_data())["rp_id"]
    rp_state = MqttClient.rp_states[rp_id].name
    await message.answer(f"ID обкатчика: {rp_id}\nСтатус обкатчика: {rp_state}\n")
    await message.answer("Настройки обкатки:" + (await get_configuration_str(rp_id)))
    await state.set_state(BotState.starting_state)
    if rp_state in ('RUNNING', 'STARTING'):
        await message.answer("Ошибка\nОбкатка уже запущена")
        return
    if rp_state == "NOT_CONNECTED":
        await message.answer("Ошибка\nОбкатчик не подключен")
        return
    await message.answer("Отправьте /cancel или /отмена чтобы отменить запуск обкатки.\
                         После запуска отправьте /stop или /стоп чтобы остановить ее")
    i = 0
    logging.info("received CMD START from user %s", message.from_user.username)
    while i < 5 and ((await state.get_state()) == BotState.starting_state):
        await message.answer(f"Запуск через {5-i}")
        i += 1
        await asyncio.sleep(1)

    if (await state.get_state()) != BotState.starting_state:
        logging.info("CMD START aborted by user")
        return

    for i in range(5):
        if (await state.get_state()) != BotState.starting_state:
            return
        MqttClient.publish_start(rp_id)
        await asyncio.sleep(1)
        if rp_id not in MqttClient.rp_states:
            await message.answer("Ошибка\n\tRaspberry Pi отключился")
            MqttClient.publish_stop(rp_id)
            return
        rp_state = MqttClient.rp_states[rp_id].name
        if rp_state == "STARTING":
            await message.answer(f"Запущено")
            break
        if rp_state == "RUNNING":
            await message.answer(f"Ошибка\n\t{rp_state}")
            MqttClient.publish_stop(rp_id)
            return
        await message.answer(f"Ошибка\n\t{rp_state}")
        logging.info("CMD START send to Raspberry Pi %d", rp_id)

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

    for rp_id in list(MqttClient.rp_states.keys()):
        conf_str = ""
        report_period = 10
        logging.info("Sending status cmd for %d", rp_id)
        MqttClient.client.publish(f"ice_runner/bot/usr_cmd/status", str(rp_id))
        await asyncio.sleep(0.5)
        header_str = html.bold(f"ID обкатчика: {rp_id}\n\tСтатус:\n" )
        data = await state.get_data()
        logging.info("Send conf command to rpi %d", rp_id)
        MqttClient.client.publish("ice_runner/bot/usr_cmd/config", str(rp_id))
        await asyncio.sleep(1)

        logging.info("Config %s", MqttClient.rp_configuration)
        if MqttClient.rp_configuration[int(rp_id)] is None:
            conf_str = html.bold("\tНет настроек обкатки\n")
        else:
            report_period = int(MqttClient.rp_configuration[int(rp_id)]["report_period"])
            conf_str = html.bold("\tНастройки обкатки:\n") + (await get_configuration_str(rp_id))
        data["rp_id"] = rp_id
        data["report_period"] = report_period
        await state.set_data(data)
        status_str, _ = await get_rp_status(int(rp_id), state)
        message_text += (header_str + status_str + conf_str)

        messages.append({"rp_id": rp_id,
                         "header": header_str,
                         "status": status_str,
                         "conf": conf_str})
        await asyncio.sleep(0.3)
    await message.answer(message_text, parse_mode=ParseMode.HTML)
    await state.set_data({})

@form_router.message(Command(commands=["status", "статус"]), ChatIdFilter())
async def command_status_handler(message: Message, state: FSMContext) -> None:
    """
    This handler receives messages with `/status` command
    """
    await state.set_state(BotState.status_state)
    data = await state.get_data()
    data["last_status_update"] = None
    if "rp_id" not in data.keys():
        await show_options(message)
        return
    rp_id = data["rp_id"]

    MqttClient.client.publish("ice_runner/bot/usr_cmd/config", str(rp_id))
    MqttClient.client.publish("ice_runner/bot/usr_cmd/state", str(rp_id))
    MqttClient.client.publish("ice_runner/bot/usr_cmd/status", str(rp_id))
    await asyncio.sleep(0.5)

    header_str = html.bold(f"ICE Runner ID: {rp_id}\n\tСтатус:\n")

    conf_str = ""
    if rp_id not in MqttClient.rp_configuration:
        conf_str = html.bold("\tНет настроек обкатки")
    else:
        conf_result = (await get_configuration_str(int(rp_id)))
        if conf_result:
            conf_str = html.bold("\tНастройки обкатки\n") + conf_result
        if "report_period" not in data:
            if "report_period" in MqttClient.rp_configuration[int(rp_id)]:
                report_period = int(MqttClient.rp_configuration[int(rp_id)]["report_period"])
            else:
                report_period = 10
            data["report_period"] = report_period
    report_period = data["report_period"]
    await state.set_data(data)
    status_str, is_updated = await get_rp_status(rp_id, state)

    message_text = header_str + status_str + conf_str
    res = await message.answer(message_text, parse_mode=ParseMode.HTML)
    await asyncio.sleep(0.5)
    while ((await state.get_state()) == BotState.status_state):
        logging.info("Updating status")
        MqttClient.client.publish("ice_runner/bot/usr_cmd/state", str(rp_id))
        MqttClient.client.publish("ice_runner/bot/usr_cmd/status", str(rp_id))
        status_str, is_updated = await get_rp_status(rp_id, state)
        if not is_updated:
            await asyncio.sleep(report_period)
            continue
        message_text = header_str + status_str + conf_str
        await res.edit_text(message_text, parse_mode=ParseMode.HTML)
        await asyncio.sleep(report_period)

@form_router.message(Command(commands=["log", "лог"]), ChatIdFilter())
async def command_log_handler(message: Message, state: FSMContext) -> None:
    """
    This handler receives messages with `/log` command
    """
    if "rp_id" not in (await state.get_data()).keys():
        await show_options(message)
        return
    rp_id = (await state.get_data())["rp_id"]
    logging.info("Getting logs for %d", rp_id)
    MqttClient.client.publish("ice_runner/bot/usr_cmd/log", str(rp_id))
    await message.answer("Пожалуйста, подождите")

@form_router.message(Command(commands=["stop", "стоп"]), ChatIdFilter())
async def command_stop_handler(message: Message, state: FSMContext) -> None:
    """
    This handler receives messages with `/stop` command
    """
    await message.answer(f"Отправляем команду остановки")
    if "rp_id" not in (await state.get_data()).keys():
        await show_options(message)
        return
    rp_id = (await state.get_data())["rp_id"]
    MqttClient.client.publish("ice_runner/bot/usr_cmd/stop", str(rp_id))
    MqttClient.client.publish("ice_runner/bot/usr_cmd/stop", str(rp_id))
    while True:
        rp_status = MqttClient.rp_states[rp_id]
        if rp_status != RunnerState.RUNNING:
            break
        await message.answer(
            f"Команда отправленна на обкатчик {rp_id}.\nТекущий статус: {rp_status.name}")
        MqttClient.client.publish("ice_runner/bot/usr_cmd/stop", str(rp_id))
        await asyncio.sleep(1)
    await message.answer(f"Остановлено")

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

@form_router.message(F.text.lower().not_in(commands_discription.keys()), ChatIdFilter())
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

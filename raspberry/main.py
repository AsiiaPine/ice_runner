import argparse
import asyncio
import logging
import os
from pathlib import Path
import sys
import datetime
from dotenv import load_dotenv
from mqtt_client import RaspberryMqttClient, start
import subprocess

sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '../dronecan_communication')))
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from common.IceRunnerConfiguration import IceRunnerConfiguration
from ice_commander import ICECommander
import logging_configurator
from can import Printer

logger = logging.getLogger(__name__)

printer = Printer("test_printer.txt", append=True)
# printer.on_message_received
conf_params_description = {
"rpm":
    {"default": 4500, "help": "Целевые обороты ДВС"},
"max-temperature":
    {"default": 190, "help": "Максимальная допустимая температура ДВС, после которой скрипт завершит выполнение"},
"max-gas-throttle":
    {"default": 100, "help": "Максимальное допустимый уровень газовой заслонки в процентах. Значение 100 означает, что нет ограничений."},
"report-period":
    {"default": 600, "help": "Период публикации статус сообщения в секундах "},
"chat-id":
    {"default": 0, "help": "Идентификатор телеграм-чата, с которым бот будет взаимодействовать."},
"time":
    {"default": 600, "help": "Время в секундах, через которое скрипт автоматически закончит свое выполнение"},
"max-vibration":
    {"default": 1000, "help": "Максимальный допустимый уровень вибрации"},
"min-fuel-volume":
    {"default": 0, "help": "Минимальный уровень топлива (процент или cm3), после которого прекращаем обкатку/выдаем предупреждение."},
"mode":
    {"default": 0, "help": "Есть 3 варианта работы: 0 - просто сразу же выставляем команду, 1 - ПИД-регулятор на стороне скрипта, 2 - ПИД-регулятор на стороне платы"},
"command":
    {"default": 0, "help": "Команда на N оборотов (RPMCommand) без ПИД-регулятора"}
}

async def main(id: int) -> None:
    print(f"RP:\tStarting raspberry {id}")
    os.environ.clear()
    dotenv_path = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), '../.env')))
    print(dotenv_path)
    load_dotenv(dotenv_path, verbose=True)
    subprocess.run(["candump", "can0", ">", f"candump_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"])
    print(os.environ.values())
    SERVER_IP = os.getenv("SERVER_IP")
    SERVER_PORT = int(os.getenv("SERVER_PORT"))
    RaspberryMqttClient.set_id(id)
    RaspberryMqttClient.connect(id, SERVER_IP, SERVER_PORT)
    ice_commander = ICECommander(reporting_period=2,
                                 configuration=IceRunnerConfiguration(args.__dict__))
    await asyncio.gather(ice_commander.run(), start())

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Raspberry Pi CAN node for automatic ICE runner')
    parser.add_argument("--id",
                        default='None',
                        type=int,
                        help="Raspberry Pi ID used for MQTT communication")
    for name, data in conf_params_description.items():
        parser.add_argument(f"--{name}",
                            default=data["default"],
                            type=int,
                            help=data["help"] + "\n\n По умолчанию: " + str(data["default"]))
    args = parser.parse_args()
    if args.id is None:
        print("RP:\tNo ID provided, reading from environment variable")
        args.id = int(os.getenv("RASPBERRY_ID"))
    if args.id is None:
        print("RP:\tNo ID provided, exiting")
        sys.exit(-1)
    os.system("echo ''")

    configuration = IceRunnerConfiguration(args.__dict__)
    RaspberryMqttClient.configuration = configuration
    asyncio.run(main(args.id))

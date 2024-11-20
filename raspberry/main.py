import argparse
import asyncio
from asyncio import subprocess
import logging
import os
import sys
import time

from dotenv import load_dotenv
import dronecan
from mqtt_client import RaspberryMqttClient, start

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

def msg_handler(msg: dronecan.node.TransferEvent) -> None:
    with open("test.txt", "a") as myfile:
        myfile.write(dronecan.to_yaml(msg))

def dump_can_messages(node: dronecan.node.Node) -> None:
    node_monitor = dronecan.app.node_monitor.NodeMonitor(node)
    # callback for printing all messages in human-readable YAML format.
    # node.add_handler(None, lambda msg: print(dronecan.to_yaml(msg)))
    node.add_handler(None, msg_handler)

async def main(id: int) -> None:
    print(f"RP:\tStarting raspberry {id}")
    load_dotenv()
    RaspberryMqttClient.set_id(id)
    RaspberryMqttClient.connect(id, "localhost", 1883)
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

import argparse
import asyncio
import logging
import os
import sys

from dotenv import load_dotenv
import dronecan
from mqtt_client import RaspberryMqttClient, start
from raccoonlab_tools.dronecan.global_node import DronecanNode
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '../dronecan_communication')))
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# from dronecan_commander import DronecanCommander
from common.IceRunnerConfiguration import IceRunnerConfiguration
from ice_commander import DronecanCommander
logger = logging.getLogger(__name__)

conf_params_description = {
"trust-pct":
    {"default": 0, "description": "Тяга в процентах"},
"rpm":
    {"default": 4500, "description": "Целевые обороты ДВС"},
"max-temperature":
    {"default": 190, "description": "Максимальная допустимая температура ДВС, после которой скрипт завершит выполнение"},
"max-gas-throttle":
    {"default": 100, "description": "Максимальное допустимый уровень газовой заслонки в процентах. Значение 100 означает, что нет ограничений."},
"report-period":
    {"default": 600, "description": "Период публикации статус сообщения в секундах "},
"chat-id":
    {"default": 0, "description": "Идентификатор телеграм-чата, с которым бот будет взаимодействовать."},
"time":
    {"default": 600, "description": "Время в секундах, через которое скрипт автоматически закончит свое выполнение"},
"max-vibration":
    {"default": 1000, "description": "Максимальный допустимый уровень вибрации"},
"min-fuel-volume":
    {"default": 0, "description": "Минимальный уровень топлива (% или cm3), после которого прекращаем обкатку/выдаем предупреждение."}
}

async def main(id: int) -> None:
    print(f"RP:\tStarting raspberry {id}")
    load_dotenv()
    # RaspberryMqttClient.set_id(id)
    # RaspberryMqttClient.connect(id, "localhost", 1883)
    node = DronecanNode()
    commander = DronecanCommander(node.node)
    commander.run()
    # DronecanCommander.connect()
    # dump_can_messages(DronecanCommander.node.node)
    # await asyncio.gather(start(), commander.run())

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Raspberry Pi CAN node for automatic ICE runner')
    parser.add_argument("--id",
                        default='None',
                        type=int,
                        help="Raspberry Pi ID используется для общения по сети. Должен быть уникальным для каждого Raspberry Pi",
                        required=True)
    for name, data in conf_params_description.items():
        parser.add_argument(f"--{name}",
                            default=data["default"],
                            type=int,
                            help=data["description"])
    args = parser.parse_args()
    if args.id is None:
        print("RP:\tNo ID provided, reading from environment variable")
        args.id = int(os.getenv("RASPBERRY_ID"))
    if args.id is None:
        print("RP:\tNo ID provided, exiting")
        sys.exit(-1)
    configuration = IceRunnerConfiguration(args.__dict__)
    DronecanCommander.configuration = configuration
    RaspberryMqttClient.configuration = configuration
    asyncio.run(main(args.id))

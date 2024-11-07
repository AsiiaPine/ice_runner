import argparse
import asyncio
import logging
import os
import sys
import time

from dotenv import load_dotenv
from mqtt_client import RaspberryMqttClient, start
# from dronecan_communication.nodes_communicator import NodesCommunicator

sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '../dronecan_communication')))
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# import dronecan_communication.DronecanMessages as messages
from dronecan_commander import DronecanCommander
# from dronecan_communication.nodes_configurator import NodesParametersParser
import logging_configurator
logger = logging.getLogger(__name__)

async def main(id: int) -> None:
    print(f"RP:\tStarting raspberry {id}")
    load_dotenv()
    RaspberryMqttClient.set_id(id)
    RaspberryMqttClient.connect(id, "localhost", 1883)
    DronecanCommander.connect()
    await asyncio.gather(start(), DronecanCommander.run())
    # mqtt_client = RaspberryMqttClient(f"raspberry_{id}", os.getenv("SERVER_IP"), 1882)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Raspberry Pi CAN node for automatic ICE runner')
    parser.add_argument("--id",
                        default='None',
                        type=int,
                        help="Raspberry Pi ID used for MQTT communication")
    args = parser.parse_args()
    if args.id is None:
        print("RP:\tNo ID provided, reading from environment variable")
        args.id = int(os.getenv("RASPBERRY_ID"))
    if args.id is None:
        print("RP:\tNo ID provided, exiting")
        sys.exit(-1)
    asyncio.run(main(args.id))

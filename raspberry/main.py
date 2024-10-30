import argparse
import logging
import os
import sys
import time

from dotenv import load_dotenv
from mqtt_client import RaspberryMqttClient
import dronecan_communication.DronecanMessages as messages
from dronecan_communication.nodes_communicator import NodesCommunicator

sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '../dronecan_communication')))
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from dronecan_communication.nodes_communicator import NodesCommunicator
logger = logging.getLogger(__name__)

def main(id: int) -> None:
    print(f"Starting raspberry {id}")
    load_dotenv()
    is_started = False
    communicator = NodesCommunicator(mes_timeout_sec=2.0)
    communicator.set_parameters_to_nodes(parameters_dir="default_params")
    mqtt_client = RaspberryMqttClient("raspberry", os.getenv("SERVER_IP"), 1883)
    while mqtt_client.received_messages["commands"][-1] == None:
        time.sleep(1)
    print("Configuration received")

    stop_message = messages.ESCRPMCommand(command=[0, 0, 0])

    while True:
        if mqtt_client.received_messages["commands"][-1] == "start":
            print("Start")
            communicator.broadcast_message(message=messages.ESCRPMCommand(command=[1000, 1000, 1000]), timeout_sec=2.0)
            is_started = True
            return
        if mqtt_client.received_messages["commander"][-1] == "stop":
            print("Stop")
            communicator.send_message(message=stop_message, node_id=39, timeout_sec=2.0)
            is_started = False
            return
        if is_started:
            communicator.broadcast_message(message=messages.ESCRPMCommand(command=[1000, 1000, 1000]), timeout_sec=2.0)
        else:
            communicator.broadcast_message(message=messages.ESCRPMCommand(command=[0, 0, 0]), timeout_sec=2.0)
        if mqtt_client.last_message_receive_time + 10 < time.time():
            print("No message received for 10 seconds")
            mqtt_client.reconnect()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Raspberry Pi CAN node for automatic ICE runner')
    parser.add_argument("--id",
                        default='0',
                        type=int,
                        help="Raspberry Pi ID used for MQTT communication")
    args = parser.parse_args()
    
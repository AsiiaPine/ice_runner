import argparse
import logging
import os
import sys
import time

from dotenv import load_dotenv
from mqtt_client import RaspberryMqttClient
# from dronecan_communication.nodes_communicator import NodesCommunicator

sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '../dronecan_communication')))
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import dronecan_communication.DronecanMessages as messages
from dronecan_commander import DronecanCommander
from dronecan_communication.nodes_configurator import NodesParametersParser
logger = logging.getLogger(__name__)

def main(id: int) -> None:
    print(f"RP:\tStarting raspberry {id}")
    load_dotenv()
    is_started = False
    # TODO: change port
    mqtt_client = RaspberryMqttClient(id, "localhost", 1883)
    # mqtt_client = RaspberryMqttClient(f"raspberry_{id}", "localhost"os.getenv("SERVER_IP"), 1883)
    # mqtt_client = RaspberryMqttClient(f"raspberry_{id}", os.getenv("SERVER_IP"), 1882)
    print(mqtt_client.received_messages[f"raspberry_{id}_commander"])
    while not mqtt_client.received_messages[f"raspberry_{id}_commander"]:
        time.sleep(1)
        mqtt_client.publish(f"raspberry_pi", "ready")
        print("RP:\tNo message received yet")
    print("RP:\tGot start message")
    dronecan_commander = DronecanCommander()
    # parameters = NodesParametersParser('default_params').convert_parameters_to_dronecan()
    while True:
        if mqtt_client.received_messages[f"raspberry_{id}_commander"][-1] == f"start":
            print("RP:\tStart")
            is_started = True
        if mqtt_client.received_messages[f"raspberry_{id}_commander"][-1] == f"stop" or mqtt_client.received_messages["commander"][-1] == f"stop_all":
            print("RP:\tStop")
            is_started = False
        if mqtt_client.last_message_receive_time + 10 < time.time():
            print("RP:\tNo message received for 10 seconds")
            mqtt_client.reconnect()
            is_started = False
        if is_started:
            dronecan_commander.set_rpm(1000)
        else:
            dronecan_commander.set_rpm(0)
        dronecan_commander.run()

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
    main(args.id)

import asyncio
import logging
import os
import sys
import time
from typing import Any, Dict
from dotenv import load_dotenv
from paho.mqtt.client import MQTTv311
from server_mqtt_client import ServerMqttClient, start

sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '../common')))
config_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'last_config.yml'))
logger = logging.getLogger(__name__)
configuration: Dict[str, Any] = {}
connected_nodes = {'ice': [], 'mini': []}
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
SERVER_IP = os.getenv("SERVER_IP")
SERVER_PORT = int(os.getenv("SERVER_PORT"))

def start_server() -> None:
    ServerMqttClient.connect(SERVER_IP, SERVER_PORT)
    start()
    last_keep_alive = time.time()
    while True:
        if time.time() - last_keep_alive > 1:
            for rp_id, status in ServerMqttClient.rp_status.items():
                topic = f"ice_runner/server/raspberry_pi_commander/{rp_id}/command"
                ServerMqttClient.client.publish(topic, "keep alive").wait_for_publish()
                # ServerMqttClient.analyse_rp_messages(rp_id)
                ServerMqttClient.publish_rp_states()
                # ServerMqttClient.control_ice_runner(rp_id)

            last_keep_alive = time.time()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    start_server()

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

def start_server() -> None:
    ServerMqttClient.connect("localhost", 1883)
    start()
    last_keep_alive = time.time()
    while True:
        if time.time() - last_keep_alive > 1:
            for rp_id, status in ServerMqttClient.rp_status.items():
                topic = f"ice_runner/server/raspberry_pi_commander/{rp_id}/command"
                ServerMqttClient.client.publish(topic, "keep alive").wait_for_publish()
                ServerMqttClient.analyse_rp_messages(rp_id)
                # ServerMqttClient.client.publish(f"ice_runner/server/raspberry_pi_commander/{rp_id}/
                # command", "keep alive").wait_for_publish()
            last_keep_alive = time.time()
        # ServerMqttClient.client.publish(f"ice_runner/server/raspberry_pi_commander/1/command", "keep alive").wait_for_publish()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    start_server()

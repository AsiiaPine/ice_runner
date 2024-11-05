import asyncio
import logging
import os
import sys
import time
from typing import Any, Dict
from dotenv import load_dotenv
from paho.mqtt.client import MQTTv311
from server_mqtt_client import ServerMqttClient

config_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'last_config.yml'))
logger = logging.getLogger(__name__)
configuration: Dict[str, Any] = {}
connected_nodes = {'ice': [], 'mini': []}
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

async def start_server() -> None:
    # server_mqtt_client = ServerMqttClient("server")
    print("made server connection")
    ServerMqttClient.connect()
    # last_ready_transmit = time.time()
    # while True:
        # await ServerMqttClient.publish_state()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(start_server())

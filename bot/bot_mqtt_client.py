import os
import sys
from typing import Any, Dict
from paho import mqtt
from paho.mqtt.client import MQTTv311, Client
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from common.RPStates import RPStates, safe_literal_eval
import logging
import logging_configurator
logger = logging_configurator.AsyncLogger(__name__)

class BotMqttClient:
    client = Client(client_id="bot", clean_session=True, userdata=None, protocol=MQTTv311, reconnect_on_failure=True)
    rp_states: Dict[int, str] = {}
    rp_status: Dict[int, str] = {}
    rp_configuration: Dict[int, Dict[str, Any]] = {}

    @classmethod
    async def connect(cls, server_ip: str = "localhost", port: int = 1883, max_messages: int = 10) -> None:
        cls.client = Client(client_id="bot", clean_session=True, userdata=None, protocol=MQTTv311, reconnect_on_failure=True)
        cls.client.connect(server_ip, port, 60)
        cls.client.publish("ice_runner/bot", "ready")

    @classmethod
    def get_client(cls) -> mqtt.client.Client:
        return cls.client

def handle_commander_state(client, userdata, message):
    rp_pi_id = int(message.topic.split("/")[-2])
    BotMqttClient.rp_states[rp_pi_id] = safe_literal_eval(message.payload.decode())
    BotMqttClient.rp_states[rp_pi_id] = RPStates(int(BotMqttClient.rp_states[rp_pi_id]))
    logger.info(f"STATUS\t| received RP state from Raspberry Pi {rp_pi_id}")

def handle_commander_status(client, userdata, message):
    rp_pi_id = int(message.topic.split("/")[-2])
    state = safe_literal_eval(message.payload.decode())
    if state is not None:
        BotMqttClient.rp_status[rp_pi_id] = state
        logger.info(f"STATUS\t| received RP status from Raspberry Pi {rp_pi_id}")

def handle_commander_config(client, userdata, message):
    rp_pi_id = int(message.topic.split("/")[-2])
    BotMqttClient.rp_configuration[rp_pi_id] = safe_literal_eval(message.payload.decode())
    logger.info(f"STATUS\t| received RP configuration from Raspberry Pi {rp_pi_id}")

async def start() -> None:
    print("start")
    BotMqttClient.client.message_callback_add("ice_runner/server/bot_commander/rp_states/+/state", handle_commander_state)
    BotMqttClient.client.message_callback_add("ice_runner/server/bot_commander/rp_states/+/status", handle_commander_status)
    BotMqttClient.client.message_callback_add("ice_runner/server/bot_commander/rp_states/+/config", handle_commander_config)
    BotMqttClient.client.subscribe("ice_runner/server/bot_commander/#")
    BotMqttClient.client.loop_start()

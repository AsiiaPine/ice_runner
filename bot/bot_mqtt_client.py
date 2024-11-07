import ast
from typing import Any, Dict
from paho import mqtt
from paho.mqtt.client import MQTTv311, Client


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
        print("BotMqttClient connected")

    @classmethod
    def get_client(cls) -> mqtt.client.Client:
        return cls.client

    @classmethod
    def allocate_data(cls, rp_id: int) -> None:
        if rp_id in cls.rp_states.keys():
            cls.rp_states[rp_id] = None
        if rp_id in cls.rp_status.keys():
            cls.rp_status[rp_id] = None
        if rp_id in cls.rp_configuration.keys():
            cls.rp_configuration[rp_id] = None

def handle_commander_state(client, userdata, message):
    rp_pi_id = int(message.topic.split("/")[-2])
    BotMqttClient.allocate_data(rp_pi_id)
    BotMqttClient.rp_states[rp_pi_id] = message.payload.decode()

def handle_commander_stats(client, userdata, message):
    rp_pi_id = int(message.topic.split("/")[-2])
    BotMqttClient.allocate_data(rp_pi_id)
    BotMqttClient.rp_status[rp_pi_id] = message.payload.decode()

def handle_commander_config(client, userdata, message):
    rp_pi_id = int(message.topic.split("/")[-2])
    BotMqttClient.allocate_data(rp_pi_id)
    BotMqttClient.rp_configuration[rp_pi_id] = ast.literal_eval(message.payload.decode())

async def start() -> None:
    print("start")
    BotMqttClient.client.message_callback_add("ice_runner/server/bot_commander/rp_states/+/state", handle_commander_state)
    BotMqttClient.client.message_callback_add("ice_runner/server/bot_commander/rp_states/+/stats", handle_commander_stats)
    BotMqttClient.client.subscribe("ice_runner/server/bot_commander/#")
    BotMqttClient.client.loop_start()

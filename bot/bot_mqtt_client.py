from typing import Any, Dict
from paho import mqtt
from paho.mqtt.client import MQTTv311, Client


class BotMqttClient:
    # client: AsyncioPahoClient = None
    client = Client(client_id="bot", clean_session=True, userdata=None, protocol=MQTTv311, reconnect_on_failure=True)
    rp_states: Dict[int, str] = {}
    rp_status: Dict[int, str] = {}

    @classmethod
    async def connect(cls, server_ip: str = "localhost", port: int = 1883, max_messages: int = 10) -> None:
        cls.client = Client(client_id="bot", clean_session=True, userdata=None, protocol=MQTTv311, reconnect_on_failure=True)
        cls.client.connect(server_ip, port, 60)
        cls.client.publish("ice_runner/bot", "ready")
        print("BotMqttClient connected")

    @classmethod
    def get_client(cls) -> mqtt.client.Client:
        return cls.client

def handle_commander_state(client, userdata, message):
    print(f"Bot received message user:{userdata} {message.topic}: {message.payload.decode()}")
    rp_pi_id = int(message.topic.split("/")[-2])
    BotMqttClient.rp_states[rp_pi_id] = message.payload.decode()

def handle_commander_stats(client, userdata, message):
    print(f"Bot received message user:{userdata} {message.topic}: {message.payload.decode()}")
    rp_pi_id = int(message.topic.split("/")[-2])
    BotMqttClient.rp_status[rp_pi_id] = message.payload.decode()

async def start() -> None:
    print("start")
    BotMqttClient.client.message_callback_add("ice_runner/server/bot_commander/rp_states/+/state", handle_commander_state)
    BotMqttClient.client.message_callback_add("ice_runner/server/bot_commander/rp_states/+/stats", handle_commander_stats)
    BotMqttClient.client.subscribe("ice_runner/server/bot_commander/#")
    BotMqttClient.client.loop_start()

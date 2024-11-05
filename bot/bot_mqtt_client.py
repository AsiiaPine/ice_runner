import asyncio
import yaml
import ast
# from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Dict

from paho import mqtt
from paho.mqtt.client import MQTTv311, Client
from asyncio_paho import AsyncioPahoClient

async def dummy():
    pass

class BotMqttClient:
    client = AsyncioPahoClient(client_id="bot", clean_session=True, userdata=None, protocol=MQTTv311, reconnect_on_failure=True, loop=dummy)
    # client = Client(client_id="bot", clean_session=True, userdata=None, protocol=MQTTv311, reconnect_on_failure=True)
    rp_states: Dict[int, str] = {}
    rp_status: Dict[int, str] = {}

    @classmethod
    async def connect(cls, server_ip: str = "localhost", port: int = 1883, max_messages: int = 10) -> None:
        async with AsyncioPahoClient(client_id="bot", clean_session=True, userdata=None, protocol=MQTTv311, reconnect_on_failure=True) as client:
            cls.client = client
            # cls.client = AsyncioPahoClient()
            await cls.client.asyncio_connect(server_ip, port, 60)
            await cls.client.asyncio_publish("ice_runner/bot", "ready")
            print("BotMqttClient connected")

    @classmethod
    def get_client(cls) -> mqtt.client.Client:
        return cls.client

# @BotMqttClient.client.topic_callback(f"ice_runner/server/bot_commander/rp_states/+/state")
async def handle_commander_state(client, userdata, message):
    print(f"Bot received message user:{userdata} {message.topic}: {message.payload.decode()}")
    rp_pi_id = int(message.topic.split("/")[-2])
    BotMqttClient.rp_states[rp_pi_id] = message.payload.decode()

# @BotMqttClient.client.topic_callback(f"ice_runner/server/bot_commander/rp_states/+/stats")
async def handle_commander_stats(client, userdata, message):
    print(f"Bot received message user:{userdata} {message.topic}: {message.payload.decode()}")
    rp_pi_id = int(message.topic.split("/")[-2])
    BotMqttClient.rp_status[rp_pi_id] = message.payload.decode()

async def start() -> None:
    BotMqttClient.client.asyncio_listeners.message_callback_add("ice_runner/bot_commander/rp_states/+/state", handle_commander_state)
    BotMqttClient.client.asyncio_listeners.message_callback_add("ice_runner/bot_commander/rp_states/+/stats", handle_commander_stats)
    await BotMqttClient.client.asyncio_subscribe("ice_runner/server/bot_commander/#")
    # BotMqttClient.client.asyncio_listeners.("ice_runner/server/bot_commander/#")

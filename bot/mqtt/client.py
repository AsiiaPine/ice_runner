"""The module defines mqtt client for telegram bot"""

# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import os
import sys
import logging
from typing import Any, Dict
from paho.mqtt.client import MQTTv311, Client
from common.RPStates import RunnerState

class MqttClient:
    """The class is used to connect Bot to MQTT broker"""
    client = Client(client_id="bot", clean_session=True,
                    userdata=None, protocol=MQTTv311, reconnect_on_failure=True)
    rp_states: Dict[int, RunnerState] = {}
    rp_status: Dict[int, Dict[str, Any]] = {}
    rp_logs: Dict[int, str] = {}
    rp_configuration: Dict[int, Dict[str, Any]] = {}
    rp_stop_handlers: Dict[int, str] = {}
    server_connected = False

    @classmethod
    async def connect(cls, server_ip: str = "localhost", port: int = 1883) -> None:
        """The function connects client to MQTT server"""
        cls.client.connect(server_ip, port, 60)
        cls.client.publish("ice_runner/bot", "ready")
        logging.info("started bot on %s:%d", server_ip, port)

    @classmethod
    async def start(cls) -> None:
        """The function subscribe ServerMqttClient to commander topics
            and starts new thread to process network traffic"""
        cls.client.subscribe("ice_runner/server/bot_commander/#")
        cls.client.loop_start()

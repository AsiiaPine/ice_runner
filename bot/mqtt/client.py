#!/usr/bin/env python3
# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import logging
import os
import sys
from typing import Any, Dict
from paho.mqtt.client import MQTTv311, Client
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from common.RPStates import RPFlags

class MqttClient:
    client = Client(client_id="bot", clean_session=True, userdata=None, protocol=MQTTv311, reconnect_on_failure=True)
    rp_states: Dict[int, RPFlags] = {}
    rp_status: Dict[int, str] = {}
    rp_logs: Dict[int, str] = {}
    rp_configuration: Dict[int, Dict[str, Any]] = {}
    server_connected = False

    @classmethod
    async def connect(cls, server_ip: str = "localhost", port: int = 1883) -> None:
        cls.client = Client(client_id="bot", clean_session=True, userdata=None, protocol=MQTTv311, reconnect_on_failure=True)
        cls.client.connect(server_ip, port, 60)
        cls.client.publish("ice_runner/bot", "ready")
        logging.getLogger(__name__).info("started bot on " + server_ip + ":" + str(port))

    @classmethod
    def get_client(cls) -> Client:
        return cls.client

    @classmethod
    async def start(cls) -> None:
        cls.client.subscribe("ice_runner/server/bot_commander/#")
        cls.client.loop_start()

#!/usr/bin/env python3
# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import datetime
import logging
import os
import sys
import time
from typing import Any, Dict
from dotenv import load_dotenv
from paho.mqtt.client import MQTTv311
from server_mqtt_client import ServerMqttClient, start
import logging_configurator
logger = logging_configurator.getLogger(__file__)
from pathlib import Path


def start_server() -> None:
    os.environ.clear()
    load_dotenv()
    TOKEN = os.getenv("BOT_TOKEN")
    SERVER_IP = os.getenv("SERVER_IP")
    SERVER_PORT = int(os.getenv("SERVER_PORT"))

    while True:
        ServerMqttClient.connect(SERVER_IP, SERVER_PORT)
        logger.info("Started")
        start()
        last_keep_alive = 0
        while ServerMqttClient.client.is_connected: #wait in loop
            if time.time() - last_keep_alive > 0.5:
                for i in ServerMqttClient.rp_status.keys():
                    ServerMqttClient.client.publish(f"ice_runner/server/rp_commander/{i}/command", "keep alive")
                last_keep_alive = time.time()
            pass
        logger.error("STATUS\t| Disconnected")
        ServerMqttClient.client.disconnect() # disconnect
        ServerMqttClient.client.loop_stop()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    start_server()

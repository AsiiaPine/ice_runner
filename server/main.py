#!/usr/bin/env python3
# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import logging
import os
import sys
import time
from dotenv import load_dotenv
from mqtt.handlers import ServerMqttClient
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import logging_configurator

logger = logging_configurator.getLogger(__file__)

def start_server() -> None:
    os.environ.clear()
    load_dotenv()
    ServerIP = os.getenv("SERVER_IP")
    ServerPort = int(os.getenv("SERVER_PORT"))

    while True:
        ServerMqttClient.connect(ServerIP, ServerPort)
        logger.info("Started")
        ServerMqttClient.start()

        last_keep_alive = 0
        while ServerMqttClient.client.is_connected: #wait in loop
            if time.time() - last_keep_alive > 0.5:
                for i in ServerMqttClient.rp_status.keys():
                    ServerMqttClient.client.publish(
                                        f"ice_runner/server/rp_commander/{i}/command", "keep alive")
                last_keep_alive = time.time()
            pass
        logger.error("STATUS\t| Disconnected")
        ServerMqttClient.client.disconnect() # disconnect
        ServerMqttClient.client.loop_stop()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    start_server()

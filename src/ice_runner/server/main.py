#!/usr/bin/env python3
# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

"""The script is used to start the server"""

import os
import sys
import time
import logging

import argparse
from dotenv import load_dotenv
from server.mqtt.handlers import ServerMqttClient
from common import logging_configurator

def main() -> None:
    """The function starts the server"""
    load_dotenv()
    server_ip = os.getenv("SERVER_IP")
    server_port = int(os.getenv("SERVER_PORT"))

    while True:
        ServerMqttClient.connect(server_ip, server_port)
        logging.info("Started")
        ServerMqttClient.start()

        last_keep_alive = 0
        while ServerMqttClient.client.is_connected: #wait in loop
            if time.time() - last_keep_alive > 0.5:
                for i in ServerMqttClient.rp_status:
                    ServerMqttClient.client.publish(
                                        f"ice_runner/server/rp_commander/{i}/command", "keep alive")
                last_keep_alive = time.time()
        logging.error("STATUS\t| Disconnected")
        ServerMqttClient.client.disconnect() # disconnect
        ServerMqttClient.client.loop_stop()

def start(log_dir: str, args: list['str'] = None) -> None:
    logging_configurator.get_logger(__file__, log_dir)
    parser = argparse.ArgumentParser()
    # Should just trip on non-empty arg and do nothing otherwise
    parser.parse_args(args)
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    main()

if __name__ == "__main__":
    start(os.getcwd())

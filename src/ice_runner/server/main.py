#!/usr/bin/env python3
# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

"""The script is used to start the server"""

import asyncio
import os
import time
import logging

import argparse
from dotenv import load_dotenv
from server.mqtt.handlers import ServerMqttClient
from common import logging_configurator

last_keep_alive = 0
async def ping_rpis() -> None:
    """The function sends ping messages to all Raspberry Pis"""
    global last_keep_alive
    if time.time() - last_keep_alive > 0.5:
        for i in ServerMqttClient.rp_status:
            ServerMqttClient.client.publish(
                                f"ice_runner/server/rp_commander/{i}/command", "keep alive")
        last_keep_alive = time.time()

async def main() -> None:
    """The function starts the server"""
    os.environ.clear()
    load_dotenv()
    server_ip = os.getenv("SERVER_IP")
    server_port = int(os.getenv("SERVER_PORT"))
    ServerMqttClient.connect(server_ip, server_port)
    await ServerMqttClient.start()
    logging.info("Started")

    while True:
        try:
            await ping_rpis()
            await asyncio.sleep(1)
        except RuntimeError as e:
            logging.error(e)
            ServerMqttClient.connect(server_ip, server_port)
            await ServerMqttClient.start()
            logging.info("Reconnected")

def start(log_dir: str, args: list['str'] = None) -> None:
    parser = argparse.ArgumentParser()
    # Should just trip on non-empty arg and do nothing otherwise
    parser.parse_args(args)
    logging_configurator.get_logger(__file__, log_dir)
    asyncio.run(main())

if __name__ == "__main__":
    start(os.getcwd())

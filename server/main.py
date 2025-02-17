#!/usr/bin/env python3
# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

"""The script is used to start the server"""

import asyncio
import os
import sys
import time
import logging
from dotenv import load_dotenv
from line_profiler import profile
from mqtt.handlers import ServerMqttClient
from common import logging_configurator
from pycallgraph2 import PyCallGraph
from pycallgraph2.output import GraphvizOutput

logger = logging_configurator.getLogger(__file__)

last_keep_alive = 0
async def ping_rpis() -> None:
    """The function sends ping messages to all Raspberry Pis"""
    global last_keep_alive
    if time.time() - last_keep_alive > 0.5:
        for i in ServerMqttClient.rp_status:
            ServerMqttClient.client.publish(
                                f"ice_runner/server/rp_commander/{i}/command", "keep alive")
        last_keep_alive = time.time()

@profile
async def main() -> None:
    """The function starts the server"""
    os.environ.clear()
    load_dotenv()
    server_ip = os.getenv("SERVER_IP")
    server_port = int(os.getenv("SERVER_PORT"))
    ServerMqttClient.connect(server_ip, server_port)
    await ServerMqttClient.start()
    logger.info("Started")

    while True:
        await ping_rpis()
        await asyncio.sleep(1)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())

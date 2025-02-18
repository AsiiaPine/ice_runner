#!/usr/bin/env python3
# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

"""The script is used to start the engine running-in."""


import os
import sys
import time
from pathlib import Path

import asyncio
import argparse
from dotenv import load_dotenv
from mqtt.handlers import MqttClient, add_handlers
from can_control.ice_commander import ICECommander
from common.IceRunnerConfiguration import IceRunnerConfiguration
from common import logging_configurator

logger = logging_configurator.getLogger(__file__)

last_sync_time = time.time()

async def main(run_id: int, configuration: IceRunnerConfiguration) -> None:
    """The function starts the ICE runner"""
    print(f"RP\t-\tStarting raspberry {run_id}")
    os.environ.clear()
    dotenv_path = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), '../.env')))
    load_dotenv(dotenv_path, verbose=True)
    server_ip = os.getenv("SERVER_IP")
    serve_port = int(os.getenv("SERVER_PORT"))
    MqttClient.connect(run_id, server_ip, serve_port)
    add_handlers()
    ice_commander = ICECommander(configuration=configuration)
    background_tasks = set()
    mqtt_task = asyncio.create_task(MqttClient.start())
    background_tasks.add(mqtt_task)
    ice_task = asyncio.create_task(ice_commander.run())
    background_tasks.add(ice_task)
    ice_task.add_done_callback(ice_commander.on_keyboard_interrupt)
    mqtt_task.add_done_callback(MqttClient.on_keyboard_interrupt)
    try:
        await asyncio.gather(*background_tasks, return_exceptions=True)
    except asyncio.CancelledError:
        ice_commander.stop()
        await asyncio.sleep(0.5)
        mqtt_task.cancel()
        await ice_commander
        await mqtt_task

        # Ensure all tasks are cleaned up before closing loop
        background_tasks.clear()

if __name__ == "__main__":
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
                                    description='Raspberry Pi CAN node for automatic ICE runner')
    parser.add_argument("--id",
                        default='None',
                        type=int,
                        help="Raspberry Pi ID used for MQTT communication")

    args: argparse.Namespace = parser.parse_args()
    if args.id is None:
        print("RP\t-\tNo ID provided, reading from environment variable")
        args.id = int(os.getenv("RASPBERRY_ID"))
    if args.id is None:
        print("RP\t-\tNo ID provided, exiting")
        sys.exit(-1)
    config = IceRunnerConfiguration(file_path="ice_configuration.yml")
    MqttClient.configuration = config
    try:
        asyncio.run(main(args.id, config))
    except KeyboardInterrupt:
        print("Received KeyboardInterrupt")
        sys.exit(0)

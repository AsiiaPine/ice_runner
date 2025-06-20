#!/usr/bin/env python3
# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

"""The script is used to start the engine running-in."""


import os
import sys
import time

import asyncio
import argparse
from dotenv import load_dotenv
from raspberry.mqtt.handlers import MqttClient, add_handlers
from raspberry.can_control.IceCommander import ICECommander
from raspberry.can_control.RunnerConfiguration import RunnerConfiguration
from raspberry.can_control.node import CanNode
from common import logging_configurator

last_sync_time = time.time()

async def main(run_id: int, configuration: RunnerConfiguration, log_dir: str) -> None:
    """The function starts the ICE runner"""
    print(f"RP\t-\tStarting raspberry {run_id}")
    load_dotenv()
    server_ip = os.getenv("SERVER_IP")
    server_port = int(os.getenv("SERVER_PORT"))
    MqttClient.connect(run_id, server_ip, server_port)
    add_handlers()
    ice_commander = ICECommander(configuration=configuration)

    mqtt_task = asyncio.create_task(MqttClient.start())
    ice_task = asyncio.create_task(ice_commander.run())

    background_tasks = {mqtt_task, ice_task}

    ice_task.add_done_callback(ice_commander.on_keyboard_interrupt)
    mqtt_task.add_done_callback(MqttClient.on_keyboard_interrupt)
    try:
        await asyncio.gather(*background_tasks)
    except asyncio.CancelledError:
        ice_commander.stop()
        await asyncio.sleep(0.5)
        mqtt_task.cancel()
        ice_task.cancel()
        await ice_task
        await mqtt_task
        # Ensure all tasks are cleaned up before closing loop
        background_tasks.clear()

def start(log_dir: str, args: list['str'] = None) -> None:
    # logging_configurator.get_logger(__file__, log_dir)
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description='Raspberry Pi CAN node for automatic ICE runner')
    parser.add_argument("--id",
                        default='-1',
                        type=int,
                        help="Raspberry Pi ID used for MQTT communication")
    parser.add_argument("--config", default="ice_configuration.yml",
                        help="Path to ICE runner configuration file")

    # This is disgusting
    CanNode.set_log_dir(log_dir)
    logging_configurator.get_logger(__file__, log_dir)

    args: argparse.Namespace = parser.parse_args(args)
    if args.id == -1:
        print("RP\t-\tNo ID provided, reading from environment variable")
        args.id = int(os.getenv("RUNNER_ID"))
    if args.id == -1:
        print("RP\t-\tNo ID provided, exiting")
        sys.exit(-1)
    config = RunnerConfiguration(file_path=args.config)
    MqttClient.configuration = config
    try:
        asyncio.run(main(args.id, config, log_dir))
    except KeyboardInterrupt:
        print("Received KeyboardInterrupt")
        sys.exit(0)

if __name__ == "__main__":
    start(os.getcwd())

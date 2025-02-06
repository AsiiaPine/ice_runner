#!/usr/bin/env python3
# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import argparse
import asyncio
import os
from pathlib import Path
import sys
import time
from dotenv import load_dotenv
import yaml
from mqtt.handlers import MqttClient
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from common.IceRunnerConfiguration import IceRunnerConfiguration
from raspberry.can_control.ice_commander import ICECommander
import logging_configurator

conf_params_description = yaml.safe_load(open('ice_configuration.yml'))

logger = logging_configurator.getLogger(__file__)

last_sync_time = time.time()

async def main(id: int) -> None:
    print(f"RP\t-\tStarting raspberry {id}")
    os.environ.clear()
    dotenv_path = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), '../.env')))
    load_dotenv(dotenv_path, verbose=True)
    SERVER_IP = os.getenv("SERVER_IP")
    SERVER_PORT = int(os.getenv("SERVER_PORT"))
    MqttClient.connect(id, SERVER_IP, SERVER_PORT)

    ice_commander = ICECommander(reporting_period=2,
                                 configuration=IceRunnerConfiguration(args.__dict__))

    await asyncio.gather(ice_commander.run(), MqttClient.start())

if __name__ == "__main__":
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description='Raspberry Pi CAN node for automatic ICE runner')
    parser.add_argument("--id",
                        default='None',
                        type=int,
                        help="Raspberry Pi ID used for MQTT communication")
    for name, data in conf_params_description.items():
        parser.add_argument(f"--{name}",
                            default=data["default"],
                            type=int,
                            help=data["help"] + "\n\n По умолчанию: " + str(data["default"]))
    args: argparse.Namespace = parser.parse_args()
    if args.id is None:
        print("RP\t-\tNo ID provided, reading from environment variable")
        args.id = int(os.getenv("RASPBERRY_ID"))
    if args.id is None:
        print("RP\t-\tNo ID provided, exiting")
        sys.exit(-1)
    configuration = IceRunnerConfiguration(args.__dict__)
    MqttClient.configuration = configuration
    asyncio.run(main(args.id))

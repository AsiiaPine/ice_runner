#!/usr/bin/env python3
# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import ast
import os
import sys
import time
from typing import Any, Dict, List
from paho import mqtt
from paho.mqtt.client import MQTTv311, Client
import yaml

sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import logging
# import logging_configurator
# logging.getLogger(__name__) = logging_configurator.AsyncLogger(__file__)

from common.IceRunnerConfiguration import IceRunnerConfiguration
from common.RPStates import RPStatesDict

def on_disconnect(client, userdata, rc):
    if rc != 0:
        logging.getLogger(__name__).error("Unexpected MQTT disconnection. Will auto-reconnect")

class RaspberryMqttClient:
    client: Client = Client(client_id="raspberry_0", clean_session=False, userdata=None, protocol=MQTTv311, reconnect_on_failure=True)
    client.disconnect_callback = on_disconnect
    rp_id: int = 0
    last_message_receive_time = 0
    setpoint_command: float = 0
    to_run: bool = 0
    to_stop: bool = 0
    state = RPStatesDict["STOPPED"]
    status: Dict[str, Any] = {}
    configuration: IceRunnerConfiguration

    @classmethod
    def get_client(cls) -> Client:
        return cls.client

    @classmethod
    def connect(cls, rp_id: int, server_ip: str, port: int = 1883, max_messages: int = 2) -> None:
        cls.is_connected = False
        cls.rp_id = rp_id
        cls.client = Client(client_id=f"raspberry_{rp_id}", clean_session=True, protocol=MQTTv311, reconnect_on_failure=True)
        logging.getLogger(__name__).info(f"Connecting to {server_ip}:{port}")
        cls.client.connect(server_ip, port, 60)
        cls.client.publish(f"ice_runner/raspberry_pi/{rp_id}/state", RPStatesDict["STOPPED"])
        logging.getLogger(__name__).info(f"PUBLISH:\tstate")

    @classmethod
    def set_id(cls, rp_id: str) -> None:
        cls.rp_id = rp_id
        cls.client._client_id = f"raspberry_{rp_id}"

    @classmethod
    def publish_messages(cls, messages: Dict[str, Any]) -> None:
        for dronecan_type in messages.keys():
            cls.client.publish(f"ice_runner/raspberry_pi/{cls.rp_id}/dronecan/{dronecan_type}", str(messages[dronecan_type]))
        logging.getLogger(__name__).info(f"PUBLISH:\tdronecan messages")

    @classmethod
    def publish_status(cls, status: Dict[str, Any]) -> None:
        logging.getLogger(__name__).info(f"PUBLISH:\tstatus")
        cls.client.publish(f"ice_runner/raspberry_pi/{cls.rp_id}/status", str(status))
        cls.status = status

    @classmethod
    def publish_state(cls, state: Dict[str, Any]) -> None:
        logging.getLogger(__name__).info(f"PUBLISH:\tstate")
        cls.client.publish(f"ice_runner/raspberry_pi/{cls.rp_id}/state", str(state))
        cls.state = state

def handle_command(client, userdata, message):
    mes_text = message.payload.decode()
    if mes_text == "start":
        logging.getLogger(__name__).info("RECEIVED:\tstart")
        RaspberryMqttClient.to_run = 1
    if mes_text == "stop":
        logging.getLogger(__name__).info("RECEIVED:\tstop")
        RaspberryMqttClient.state = RPStatesDict["STOPPING"]
        RaspberryMqttClient.to_stop = 1

    if mes_text == "keep alive":
        logging.getLogger(__name__).info("RECEIVED:\tkeep alive")
        RaspberryMqttClient.last_message_receive_time = time.time()

    if mes_text == "status":
        logging.getLogger(__name__).info("RECEIVED:\tStatus request")
        RaspberryMqttClient.publish_status(str(RaspberryMqttClient.status))

def handle_config(client, userdata, message):
    logging.getLogger(__name__).info("RECEIVED:\tConfiguration")
    RaspberryMqttClient.client.publish(f"ice_runner/raspberry_pi/{RaspberryMqttClient.rp_id}/configuration", str(RaspberryMqttClient.configuration.to_dict()))

def handle_who_alive(client, userdata, message):
    logging.getLogger(__name__).info("RECEIVED:\tWHO ALIVE")
    RaspberryMqttClient.client.publish(f"ice_runner/raspberry_pi/{RaspberryMqttClient.rp_id}/status", str(RaspberryMqttClient.status))

async def start() -> None:
    RaspberryMqttClient.client.message_callback_add(f"ice_runner/server/rp_commander/{RaspberryMqttClient.rp_id}/command", handle_command)

    RaspberryMqttClient.client.message_callback_add(f"ice_runner/server/rp_commander/config", handle_config)
    RaspberryMqttClient.client.message_callback_add(f"ice_runner/server/rp_commander/who_alive", 
    handle_who_alive)

    RaspberryMqttClient.client.subscribe(f"ice_runner/server/rp_commander/{RaspberryMqttClient.rp_id}/#")
    RaspberryMqttClient.client.subscribe(f"ice_runner/server/rp_commander/#")
    RaspberryMqttClient.client.loop_start()

#!/usr/bin/env python3
# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import os
import sys
import time
from typing import Any, Dict, List
from paho.mqtt.client import MQTTv311, Client

sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import logging

from common.IceRunnerConfiguration import IceRunnerConfiguration
from common.RPStates import RPState
connected_flag=False

def on_disconnect(client, userdata, rc):
    if rc != 0:
        logging.getLogger(__name__).error("Unexpected MQTT disconnection. Will auto-reconnect")

class RaspberryMqttClient:
    client: Client
    rp_id: int = 0
    last_message_receive_time = 0
    setpoint_command: float = 0
    to_run: bool = 0
    to_stop: bool = 0
    status: Dict[str, Any] = {}
    configuration: IceRunnerConfiguration
    state: int = -1
    rp_logs: Dict[str, str] = {}

    @classmethod
    def get_client(cls) -> Client:
        return cls.client

    @classmethod
    def connect(cls, rp_id: int, server_ip: str, port: int = 1883) -> None:
        cls.is_connected = False
        cls.rp_id = rp_id
        cls.client = Client(client_id=f"raspberry_{rp_id}", clean_session=True, protocol=MQTTv311, reconnect_on_failure=True)
        cls.client.disconnect_callback = on_disconnect

        logging.getLogger(__name__).info(f"Connecting to {server_ip}:{port}")
        cls.client.connect(server_ip, port, 60)
        cls.client.publish(f"ice_runner/raspberry_pi/{rp_id}/state", RPState.NOT_CONNECTED.name)
        logging.getLogger(__name__).info(f"PUBLISH:\tstate")

    @classmethod
    def publish_messages(cls, messages: Dict[str, Any]) -> None:
        for dronecan_type in messages.keys():
            cls.client.publish(f"ice_runner/raspberry_pi/{cls.rp_id}/dronecan/{dronecan_type}", str(messages[dronecan_type]))
        logging.getLogger(__name__).info(f"PUBLISH:\tdronecan messages")

    @classmethod
    def publish_status(cls, status: Dict[str, Any]) -> None:
        logging.getLogger(__name__).info(f"PUBLISH:\tstatus")
        RaspberryMqttClient.status = status
        cls.client.publish(f"ice_runner/raspberry_pi/{cls.rp_id}/status", str(status))

    @classmethod
    def publish_state(cls, state: int) -> None:
        logging.getLogger(__name__).info(f"PUBLISH:\tstate")
        RaspberryMqttClient.state = state
        cls.client.publish(f"ice_runner/raspberry_pi/{cls.rp_id}/state", state)

    @classmethod
    def publish_log(cls) -> None:
        logging.getLogger(__name__).info(f"PUBLISH:\tlog")
        logging.getLogger(__name__).info(f"PUBLISH:\t logs: {cls.rp_logs}")
        RaspberryMqttClient.client.publish(f"ice_runner/raspberry_pi/{cls.rp_id}/log", str(RaspberryMqttClient.rp_logs))

    @classmethod
    def publish_configuration(cls) -> None:
        logging.getLogger(__name__).info(f"PUBLISH:\tconfiguration")
        cls.client.publish(f"ice_runner/raspberry_pi/{cls.rp_id}/config", str(cls.configuration.to_dict()))

def handle_command(client, userdata, message):
    mes_text = message.payload.decode()
    if mes_text == "start":
        logging.getLogger(__name__).info("RECEIVED:\tstart")
        RaspberryMqttClient.to_run = 1
    if mes_text == "stop":
        logging.getLogger(__name__).info("RECEIVED:\tstop")
        RaspberryMqttClient.to_stop = 1

    if mes_text == "keep alive":
        logging.getLogger(__name__).info("RECEIVED:\tkeep alive")
        RaspberryMqttClient.last_message_receive_time = time.time()

    if mes_text == "status":
        logging.getLogger(__name__).info("RECEIVED:\tStatus request")
        RaspberryMqttClient.publish_status(str(RaspberryMqttClient.status))
        RaspberryMqttClient.publish_state(str(RaspberryMqttClient.state))

    if mes_text == "config":
        logging.getLogger(__name__).info("RECEIVED:\tConfiguration request")
        RaspberryMqttClient.publish_configuration()

    if mes_text == "log":
        logging.getLogger(__name__).info("RECEIVED:\tLog request")
        RaspberryMqttClient.publish_log()

def handle_who_alive(client, userdata, message):
    logging.getLogger(__name__).info("RECEIVED:\tWHO ALIVE")
    RaspberryMqttClient.client.publish(f"ice_runner/raspberry_pi/{RaspberryMqttClient.rp_id}/status", str(RaspberryMqttClient.state))
    RaspberryMqttClient.publish_configuration()

async def start() -> None:
    RaspberryMqttClient.client.message_callback_add(f"ice_runner/server/rp_commander/{RaspberryMqttClient.rp_id}/command", handle_command)

    RaspberryMqttClient.client.message_callback_add(f"ice_runner/server/rp_commander/who_alive", 
    handle_who_alive)

    RaspberryMqttClient.client.subscribe(f"ice_runner/server/rp_commander/{RaspberryMqttClient.rp_id}/#")
    RaspberryMqttClient.client.subscribe(f"ice_runner/server/rp_commander/#")
    RaspberryMqttClient.client.loop_start()

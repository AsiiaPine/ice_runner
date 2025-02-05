# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import os
import sys
import time
from typing import Any, Dict, List
from paho.mqtt.client import MQTTv311, Client
import logging

sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from common.IceRunnerConfiguration import IceRunnerConfiguration

connected_flag=False

def on_disconnect(client, userdata, rc):
    if rc != 0:
        logging.error("Unexpected MQTT disconnection. Will auto-reconnect")

class RaspberryMqttClient:
    client: Client
    run_id: int = 0
    last_message_receive_time = 0
    setpoint_command: float = 0
    to_run: bool = 0
    to_stop: bool = 0
    status: Dict[str, Any] = {}
    configuration: IceRunnerConfiguration
    state: int = -1
    run_logs: Dict[str, str] = {}

    @classmethod
    def get_client(cls) -> Client:
        return cls.client

    @classmethod
    def connect(cls, runner_id: int, server_ip: str, port: int = 1883) -> None:
        cls.is_connected = False
        cls.run_id = runner_id
        cls.client = Client(client_id=f"raspberry_{runner_id}", clean_session=True, protocol=MQTTv311, reconnect_on_failure=True)
        cls.client.disconnect_callback = on_disconnect

        logging.info(f"Connecting to {server_ip}:{port}")
        cls.client.connect(server_ip, port, 60)
        cls.client.publish(f"ice_runner/raspberry_pi/{runner_id}/state", cls.state)
        logging.debug(f"PUBLISH\t-\tstate")

    @classmethod
    def publish_messages(cls, messages: Dict[str, Any]) -> None:
        for dronecan_type in messages.keys():
            cls.client.publish(f"ice_runner/raspberry_pi/{cls.run_id}/dronecan/{dronecan_type}", str(messages[dronecan_type]))
        logging.debug(f"PUBLISH\t-\tdronecan messages")

    @classmethod
    def publish_status(cls, status: Dict[str, Any]) -> None:
        logging.debug(f"PUBLISH\t-\tstatus")
        RaspberryMqttClient.status = status
        cls.client.publish(f"ice_runner/raspberry_pi/{cls.run_id}/status", str(status))

    @classmethod
    def publish_state(cls, state: int) -> None:
        logging.debug(f"PUBLISH\t-\tstate {state}")
        RaspberryMqttClient.state = state
        cls.client.publish(f"ice_runner/raspberry_pi/{cls.run_id}/state", state)

    @classmethod
    def publish_log(cls) -> None:
        logging.debug(f"PUBLISH\t-\tlog")
        logging.debug(f"PUBLISH\t-\tlogs: {cls.run_logs}")
        RaspberryMqttClient.client.publish(f"ice_runner/raspberry_pi/{cls.run_id}/log", str(RaspberryMqttClient.run_logs))

    @classmethod
    def publish_configuration(cls) -> None:
        logging.debug(f"PUBLISH\t-\tconfiguration")
        cls.client.publish(f"ice_runner/raspberry_pi/{cls.run_id}/config", str(cls.configuration.to_dict()))

    @classmethod
    def publish_stop_reason(cls, reason: str) -> None:
        logging.info(f"PUBLISH\t-\tstop reason: {reason}")
        cls.client.publish(f"ice_runner/raspberry_pi/{cls.run_id}/stop_reason", reason)

def handle_command(client, userdata, message):
    mes_text = message.payload.decode()
    if mes_text == "start":
        logging.info("RECEIVED\t-\tstart")
        RaspberryMqttClient.to_run = 1

    if mes_text == "stop":
        logging.info("RECEIVED\t-\tstop")
        RaspberryMqttClient.to_stop = 1

    if mes_text == "keep alive":
        logging.debug("RECEIVED\t-\tkeep alive")
        RaspberryMqttClient.last_message_receive_time = time.time()

    if mes_text == "status":
        logging.info("RECEIVED\t-\tStatus request")
        RaspberryMqttClient.publish_status(RaspberryMqttClient.status)
        RaspberryMqttClient.publish_state(RaspberryMqttClient.state)

    if mes_text == "config":
        logging.info("RECEIVED\t-\tConfiguration request")
        RaspberryMqttClient.publish_configuration()

    if mes_text == "log":
        logging.info("RECEIVED\t-\tLog request")
        RaspberryMqttClient.publish_log()

def handle_who_alive(client, userdata, message):
    logging.debug("RECEIVED\t-\tWHO ALIVE")
    RaspberryMqttClient.publish_state(RaspberryMqttClient.state)
    RaspberryMqttClient.publish_status(RaspberryMqttClient.status)
    RaspberryMqttClient.publish_configuration()

async def start() -> None:
    RaspberryMqttClient.client.message_callback_add(f"ice_runner/server/rp_commander/{RaspberryMqttClient.run_id}/command", handle_command)

    RaspberryMqttClient.client.message_callback_add(f"ice_runner/server/rp_commander/who_alive", 
    handle_who_alive)

    RaspberryMqttClient.client.subscribe(f"ice_runner/server/rp_commander/{RaspberryMqttClient.run_id}/#")
    RaspberryMqttClient.client.subscribe(f"ice_runner/server/rp_commander/#")
    RaspberryMqttClient.client.loop_start()

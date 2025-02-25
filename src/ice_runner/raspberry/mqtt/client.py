"""The module defines mqtt client for raspberry pi for ICE runner project"""

# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import sys
import logging
from typing import Any, Dict
from paho.mqtt.client import MQTTv311, Client
from common.IceRunnerConfiguration import IceRunnerConfiguration

class MqttClient:
    """The class is used to connect Raspberry Pi to MQTT broker"""
    client: Client = Client(clean_session=True,
                            protocol=MQTTv311,
                            reconnect_on_failure=True)
    conf_updated = False
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
    def connect(cls, runner_id: int, server_ip: str, port: int = 1883) -> None:
        """The function connects client to MQTT server"""
        cls.run_id = runner_id

        logging.info("Connecting to %s: %s\n runner id: %d", server_ip, port, runner_id)
        cls.client.connect(server_ip, port, 60)
        cls.client.publish(f"ice_runner/raspberry_pi/{runner_id}/state", cls.state)
        logging.debug("PUBLISH\t-\tstate")

    @classmethod
    def publish_messages(cls, messages: Dict[str, Any]) -> None:
        """The function publishes dronecan messages to appropriate MQTT topic"""
        for dronecan_type in messages.keys():
            cls.client.publish(f"ice_runner/raspberry_pi/{cls.run_id}/dronecan/{dronecan_type}",
                                str(messages[dronecan_type]))
        logging.debug("PUBLISH\t-\tdronecan messages")

    @classmethod
    def publish_status(cls, status: Dict[str, Any]) -> None:
        """The function publishes status to MQTT broker"""
        logging.debug("PUBLISH\t-\tstatus")
        MqttClient.status = status
        cls.client.publish(f"ice_runner/raspberry_pi/{cls.run_id}/status", str(status))

    @classmethod
    def publish_state(cls, state: int) -> None:
        """The function publishes state to MQTT broker"""
        logging.debug("PUBLISH\t-\tstate %d", state)
        MqttClient.state = state
        cls.client.publish(f"ice_runner/raspberry_pi/{cls.run_id}/state", state)

    @classmethod
    def publish_log(cls) -> None:
        """This function should be called anytime the runner changes its log"""
        logging.debug("PUBLISH\t-\tlog")
        logging.debug("PUBLISH\t-\tlogs: %s", cls.run_logs)
        MqttClient.client.publish(f"ice_runner/raspberry_pi/{cls.run_id}/log",
                                  str(MqttClient.run_logs))

    @classmethod
    def publish_configuration(cls) -> None:
        """The function publishes IceRunnerConfiguration to MQTT broker.
            The configuration should be defined before start function is called"""
        logging.debug("PUBLISH\t-\tconfiguration")
        cls.client.publish(f"ice_runner/raspberry_pi/{cls.run_id}/config",
                           str(cls.configuration.to_dict()))

    @classmethod
    def publish_stop_reason(cls, reason: str) -> None:
        """The function should be called anytime the runner changes its state to STOPPED"""
        logging.info("PUBLISH\t-\tstop reason: %s", reason)
        cls.client.publish(f"ice_runner/raspberry_pi/{cls.run_id}/stop_reason", reason)

    @classmethod
    async def start(cls) -> None:
        """The function subscribe ServerMqttClient to commander topics
            and starts new thread to process network traffic"""
        MqttClient.client.subscribe(f"ice_runner/server/rp_commander/#")
        MqttClient.client.loop_start()

    @classmethod
    def on_keyboard_interrupt(cls):
        """The function is called when KeyboardInterrupt is received"""
        cls.publish_stop_reason("Received KeyboardInterrupt")
        cls.client.disconnect()
        sys.exit(0)

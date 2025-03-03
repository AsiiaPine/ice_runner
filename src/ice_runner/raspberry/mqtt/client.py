"""The module defines mqtt client for raspberry pi for ICE runner project"""

# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import json
import sys
import logging
from typing import Any, Dict
from paho.mqtt.client import MQTTv311, Client, MQTTMessageInfo
from paho.mqtt.enums import CallbackAPIVersion
from common.IceRunnerConfiguration import IceRunnerConfiguration
from common.RunnerState import RunnerState

class MqttClient:
    """The class is used to connect Raspberry Pi to MQTT broker"""
    client: Client = Client(callback_api_version = CallbackAPIVersion.VERSION2,
                            clean_session=True,
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
    state: RunnerState = -1
    run_logs: Dict[str, str] = {}

    @classmethod
    def connect(cls, runner_id: int, server_ip: str, port: int = 1883) -> None:
        """The function connects client to MQTT server"""
        cls.run_id = runner_id

        logging.info("Connecting to %s: %s\n runner id: %d", server_ip, port, runner_id)
        cls.client.connect(server_ip, port, 60)

    @classmethod
    def publish_messages(cls, messages: Dict[str, Any]) -> None:
        """The function publishes dronecan messages to appropriate MQTT topic"""
        for dronecan_type in messages.keys():
            cls.client.publish(f"ice_runner/raspberry_pi/{cls.run_id}/dronecan/{dronecan_type}",
                                json.dumps(messages[dronecan_type]))
        logging.debug("PUBLISH\t-\tdronecan messages")

    @classmethod
    def publish_status(cls, status: Dict[str, Any]) -> None:
        """The function publishes status to MQTT broker"""
        logging.debug("PUBLISH\t-\tstatus")
        MqttClient.status = status
        cls.client.publish(f"ice_runner/raspberry_pi/{cls.run_id}/status", json.dumps(status))

    @classmethod
    def publish_state(cls, state: RunnerState) -> None:
        """The function publishes state to MQTT broker"""
        logging.debug("PUBLISH\t-\tstate %d", state.value)
        MqttClient.state = state
        mes_info: MQTTMessageInfo = cls.client.publish(
            f"ice_runner/raspberry_pi/{cls.run_id}/state", state.value)
        mes_info.wait_for_publish(timeout=1)

    @classmethod
    def publish_log(cls) -> None:
        """This function should be called anytime the runner changes its log"""
        logging.debug("PUBLISH\t-\tlog")
        logging.debug("PUBLISH\t-\tlogs: %s", cls.run_logs)
        mes_info:MQTTMessageInfo = MqttClient.client.publish(
            f"ice_runner/raspberry_pi/{cls.run_id}/log",json.dumps(MqttClient.run_logs))
        mes_info.wait_for_publish(timeout=5)


    @classmethod
    def publish_configuration(cls) -> None:
        """The function publishes IceRunnerConfiguration to MQTT broker.
            The configuration should be defined before start function is called"""
        logging.info("PUBLISH\t-\tconfiguration")
        cls.client.publish(f"ice_runner/raspberry_pi/{cls.run_id}/config",
                           json.dumps(cls.configuration.to_dict()))

    @classmethod
    def publish_stop_reason(cls, reason: str) -> None:
        """The function should be called anytime the runner changes its state to STOPPED"""
        logging.info("PUBLISH\t-\tstop reason: %s", reason)
        mes_info:MQTTMessageInfo = cls.client.publish(
                                f"ice_runner/raspberry_pi/{cls.run_id}/stop_reason", reason)
        mes_info.wait_for_publish(timeout=5)
        cls.publish_state(RunnerState.STOPPED.value)

    @classmethod
    def publish_full_configuration(cls, full_configuration: Dict[str, Any]) -> None:
        """The function should be called at the start of the script"""
        logging.info("PUBLISH\t-\tfull configuration")
        cls.client.publish(f"ice_runner/raspberry_pi/{cls.run_id}/full_config",
                           json.dumps(full_configuration))

    @classmethod
    def publish_flags(cls, flags: Dict[str, bool]) -> None:
        """The function should be called if any flag is exceeded"""
        logging.info("PUBLISH\t-\tflags")
        cls.client.publish(f"ice_runner/raspberry_pi/{cls.run_id}/flags", str(flags))

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

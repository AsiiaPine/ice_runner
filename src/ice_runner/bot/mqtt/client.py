"""The module defines mqtt client for telegram bot"""

# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import logging
from typing import Any, Dict
from paho.mqtt.client import MQTTv311, Client
from ice_runner.common.RunnerState import RunnerState

class MqttClient:
    """The class is used to connect Bot to MQTT broker"""
    client = Client(client_id="bot", clean_session=True,
                    userdata=None, protocol=MQTTv311, reconnect_on_failure=True)
    rp_states: Dict[int, RunnerState] = {}
    rp_status: Dict[int, Dict[str, Any]] = {}
    rp_logs: Dict[int, str] = {}
    rp_configuration: Dict[int, Dict[str, Any]] = {}
    runner_full_configuration: Dict[int, Dict[str, Any]] = {}
    rp_stop_handlers: Dict[int, str] = {}
    server_connected = False

    @classmethod
    async def connect(cls, server_ip: str = "localhost", port: int = 1883) -> None:
        """The function connects client to MQTT server"""
        cls.client.connect(server_ip, port, 60)
        cls.client.publish("ice_runner/bot", "ready")
        logging.info("started bot on %s:%d", server_ip, port)

    @classmethod
    async def start(cls) -> None:
        """The function subscribe ServerMqttClient to commander topics
            and starts new thread to process network traffic"""
        cls.client.subscribe("ice_runner/server/bot_commander/#")
        cls.client.loop_start()

    @classmethod
    def publish_who_alive(cls) -> None:
        """The function publishes who_alive message to ServerMqttClient"""
        cls.client.publish(f"ice_runner/bot/usr_cmd/who_alive")
        logging.info("Published\t| who alive")

    @classmethod
    def publish_stop(cls, runner_id: int) -> None:
        """The function publishes stop message to ServerMqttClient"""
        cls.client.publish(f"ice_runner/bot/usr_cmd/stop", str(runner_id))
        logging.info("Published\t| Stop command for Runner %d", runner_id)

    @classmethod
    def publish_start(cls, runner_id: int) -> None:
        """The function publishes start message to ServerMqttClient"""
        cls.client.publish(f"ice_runner/bot/usr_cmd/start", str(runner_id))
        logging.info("Published\t| Start command for Runner %d", runner_id)

    @classmethod
    def publish_config_request(cls, runner_id: int) -> None:
        """The function publishes config_request message to ServerMqttClient"""
        cls.client.publish(f"ice_runner/bot/usr_cmd/config", str(runner_id))
        logging.info("Published\t| Request for configuration of Runner %d", runner_id)

    @classmethod
    def publish_full_config_request(cls, runner_id: int) -> None:
        """The function publishes full_config_request message to ServerMqttClient"""
        cls.client.publish(f"ice_runner/bot/usr_cmd/full_config", str(runner_id))
        logging.info("Published\t| Request for full configuration of Runner %d", runner_id)

    @classmethod
    def publish_server_request(cls) -> None:
        """The function publishes server_request message to ServerMqttClient"""
        cls.client.publish("ice_runner/bot/usr_cmd/server")
        logging.info("Published\t| Request for server")

    @classmethod
    def publish_change_config(cls, runner_id: int, param_name: str, text: str) -> None:
        """The function publishes change_config message to ServerMqttClient"""
        cls.client.publish(f"ice_runner/bot/usr_cmd/{runner_id}/change_config/{param_name}", text)
        logging.info("Published\t| New config %s value cmd for Runner %d", param_name, runner_id)

    @classmethod
    def publish_status_request(cls, runner_id: int) -> None:
        cls.client.publish(f"ice_runner/bot/usr_cmd/status", str(runner_id))
        logging.info("Published\t| Status request for Runner %d", runner_id)

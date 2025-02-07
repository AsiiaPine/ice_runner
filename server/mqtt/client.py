"""The module defines mqtt client for server"""

# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import os
import sys
import logging
from typing import Any, Dict
from paho.mqtt.client import MQTTv311, Client
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from common.IceRunnerConfiguration import IceRunnerConfiguration

def on_disconnect(client: Client, userdata: Any, rc: int) -> None:
    """The callback for mqtt client disconnection"""
    del userdata, client
    logging.error("Disconnected")
    if rc != 0:
        logging.error("Unexpected MQTT disconnection. Will auto-reconnect")

class ServerMqttClient:
    """The class for server mqtt client"""
    client: Client = Client(client_id="server",clean_session=False,
                            userdata=None, protocol=MQTTv311, reconnect_on_failure=True)
    rp_messages: Dict[int, Dict[str, Dict[str, Any]]] = {}
    rp_status: Dict[int, Any] = {}
    rp_states: Dict[int, str] = {}
    rp_cur_setpoint: Dict[int, float] = {}
    rp_logs: Dict[int, Dict[str, str]] = {}
    rp_stop_reason: Dict[int, str] = {}
    rp_configuration: Dict[int, IceRunnerConfiguration] = {}
    client.disconnect_callback = on_disconnect

    @classmethod
    def connect(cls, server_ip: str = "localhost", port: int = 1883) -> None:
        """The function connects to the server, sends ready message to both raspberry pi and bot"""
        cls.client.connect(server_ip, port, 60)
        cls.client.publish("ice_runner/server/raspberry_pi_commander", "ready")
        cls.client.publish("ice_runner/server/bot_commander", "ready")

        logging.info("started server")

    @classmethod
    def publish_rp_state(cls, rp_id: int) -> None:
        """The function publishes the state of the Raspberry Pi to the bot"""
        if rp_id not in cls.rp_status:
            logging.debug(f"Published\t| Raspberry Pi %d is not connected ", rp_id)
            return
        if cls.rp_status[rp_id] is None:
            logging.debug("Published\t| Raspberry Pi %d no state set", rp_id)
            return
        cls.client.publish(f"ice_runner/server/bot_commander/rp_states/{rp_id}/state",
                           cls.rp_states[rp_id])

    @classmethod
    def publish_rp_status(cls, rp_id: int) -> None:
        """The function publishes the status of the Raspberry Pi to the bot"""
        if rp_id not in cls.rp_status:
            logging.debug("Published\t| Raspberry Pi is not connected")
            return
        status = cls.rp_status[rp_id]
        cls.client.publish(f"ice_runner/server/bot_commander/rp_states/{rp_id}/status", str(status))
        logging.debug("Published\t| Raspberry Pi %d status", rp_id)
        cls.rp_status[rp_id] = None

    @classmethod
    def publish_rp_states(cls) -> None:
        """The function publishes state and status of all Raspberry Pis to the bot"""
        for rp_id in cls.rp_status:
            cls.publish_rp_state(rp_id)
            cls.publish_rp_status(rp_id)

    @classmethod
    def start(cls) -> None:
        """The function starts the server mqtt client and subscribes to the topics"""
        logging.info("Started")
        cls.client.subscribe("ice_runner/raspberry_pi/#")
        cls.client.subscribe("ice_runner/bot/#")
        cls.client.loop_start()

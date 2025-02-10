"""The module defines callbacks for the MQTT client"""

# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import time
import logging

from mqtt.client import MqttClient

@MqttClient.client.topic_callback("ice_runner/server/rp_commander/#")
def handle_command(client, userdata, message):
    """The function handles the command from the server"""
    del userdata, client
    mes_text = message.payload.decode()
    if mes_text == "start":
        logging.info("RECEIVED\t-\tstart")
        MqttClient.to_run = 1

    if mes_text == "stop":
        logging.info("RECEIVED\t-\tstop")
        MqttClient.to_stop = 1

    if mes_text == "keep alive":
        logging.debug("RECEIVED\t-\tkeep alive")
        MqttClient.last_message_receive_time = time.time()

    if mes_text == "status":
        logging.info("RECEIVED\t-\tStatus request")
        MqttClient.publish_status(MqttClient.status)
        MqttClient.publish_state(MqttClient.state)
        MqttClient.publish_configuration()

    if mes_text == "config":
        logging.info("RECEIVED\t-\tConfiguration request")
        MqttClient.publish_configuration()

    if mes_text == "log":
        logging.info("RECEIVED\t-\tLog request")
        MqttClient.publish_log()

@MqttClient.client.topic_callback("ice_runner/server/rp_commander/who_alive")
def handle_who_alive(client, userdata, message):
    """Handler of message used to check all connected ICE Runners. All RPi should reply"""
    del userdata, message, client
    logging.debug("RECEIVED\t-\tWHO ALIVE")
    MqttClient.publish_state(MqttClient.state)

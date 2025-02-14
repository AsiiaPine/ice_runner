"""The module defines callbacks for the MQTT client"""

# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import time
import logging
from mqtt.client import MqttClient

def handle_command(client, userdata, message):
    """The function handles the command from the server"""
    del userdata, client
    logging.debug("RECEIVED\t-\t%s", message.topic)
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

def handle_change_config(client, userdata, message):
    """The function handles the change_config command from the server"""
    del userdata, client
    param_name = message.topic.split("/")[-1]
    param_value = message.payload.decode()
    logging.info("RECEIVED\t-\tparam value %s\t%s", param_name, param_value)
    try:
        MqttClient.conf_updated = True
        type_of_param = type(getattr(MqttClient.configuration, param_name))
        setattr(MqttClient.configuration, param_name, type_of_param(param_value))
    except AttributeError:
        logging.error("RECEIVED\t-\t%s\t%s\tERROR\tAttribute not found", param_name, param_value)

def handle_who_alive(client, userdata, message):
    """Handler of message used to check all connected ICE Runners. All RPi should reply"""
    del userdata, message, client
    logging.debug("RECEIVED\t-\tWHO ALIVE")
    MqttClient.publish_state(MqttClient.state)

def add_handlers() -> None:
    """The function adds handlers to the MQTT client"""
    MqttClient.client.message_callback_add(
        f"ice_runner/server/rp_commander/{MqttClient.run_id}/command", handle_command)
    MqttClient.client.message_callback_add(
        "ice_runner/server/rp_commander/who_alive", handle_who_alive)
    MqttClient.client.message_callback_add(
        f"ice_runner/server/rp_commander/{MqttClient.run_id}/change_config/#", handle_change_config)

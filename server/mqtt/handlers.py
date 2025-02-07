# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import os
import sys
import ast
import yaml
import logging
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from common.RPStates import safe_literal_eval
from mqtt.client import ServerMqttClient
from paho.mqtt.client import Client

@ServerMqttClient.client.topic_callback("ice_runner/raspberry_pi/+/dronecan/#")
def handle_raspberry_pi_dronecan_message(client: Client, userdata,  msg):
    """The function handles dronecan messages from Raspberry Pi to Server, so anyone can read them by MQTT"""
    rp_id = int(msg.topic.split("/")[2])
    message_type: str = msg.topic.split("/")[4]
    logging.debug(f"Published\t| Raspberry Pi {rp_id} send {message_type}")
    if rp_id not in ServerMqttClient.rp_messages.keys():
        ServerMqttClient.rp_messages[rp_id] = {}
    if message_type not in ServerMqttClient.rp_messages[rp_id].keys():
        ServerMqttClient.rp_messages[rp_id][message_type] = {}
    ServerMqttClient.rp_messages[rp_id][message_type] = yaml.safe_load(msg.payload.decode())

@ServerMqttClient.client.topic_callback("ice_runner/raspberry_pi/+/status")
def handle_raspberry_pi_status(client: Client, userdata,  msg):
    rp_id = int(msg.topic.split("/")[2])
    logging.debug(f"Recieved\t| Raspberry Pi {rp_id} send status")
    ServerMqttClient.rp_status[rp_id] = safe_literal_eval(msg.payload.decode())
    client.publish(f"ice_runner/server/bot_commander/rp_states/{rp_id}/status", str(ServerMqttClient.rp_status[rp_id]))

@ServerMqttClient.client.topic_callback("ice_runner/raspberry_pi/+/state")
def handle_raspberry_pi_state(client: Client, userdata,  msg):
    rp_id = int(msg.topic.split("/")[2])
    logging.debug(f"Recieved\t| Raspberry Pi {rp_id} send state")
    client.publish(f"ice_runner/server/bot_commander/rp_states/{rp_id}/state", msg.payload.decode())

@ServerMqttClient.client.topic_callback("ice_runner/raspberry_pi/+/config")
def handle_raspberry_pi_configuration(client: Client, userdata,  msg):
    rp_id = int(msg.topic.split("/")[2])
    logging.debug(f"Received\t| Raspberry Pi {rp_id} send configuration")
    ServerMqttClient.rp_configuration[rp_id] = safe_literal_eval(msg.payload.decode())
    client.publish(f"ice_runner/server/bot_commander/rp_states/{rp_id}/config", msg.payload.decode())

@ServerMqttClient.client.topic_callback("ice_runner/raspberry_pi/+/log")
def handle_raspberry_pi_log(client: Client, userdata,  msg):
    """The function handles log messages with log filename from Raspberry Pi to Bot. Can be used if bot is running on same machine. Otherwise, send the whole log file to Bot"""
    rp_id = int(msg.topic.split("/")[2])
    logging.info(f"Received\t| Raspberry Pi {rp_id} send log")
    ServerMqttClient.rp_logs[rp_id] = msg.payload.decode()
    client.publish(f"ice_runner/server/bot_commander/rp_states/{rp_id}/log", str(ServerMqttClient.rp_logs[rp_id]))

@ServerMqttClient.client.topic_callback("ice_runner/raspberry_pi/+/stop_reason")
def handle_raspberry_pi_stop_reason(client: Client, userdata,  msg):
    rp_id = int(msg.topic.split("/")[2])
    logging.info(f"Received\t| Raspberry Pi {rp_id} send stop reason")
    ServerMqttClient.rp_stop_reason[rp_id] = msg.payload.decode()
    client.publish(f"ice_runner/server/bot_commander/rp_states/{rp_id}/stop_reason", ServerMqttClient.rp_stop_reason[rp_id])

@ServerMqttClient.client.topic_callback("ice_runner/bot/usr_cmd/log")
def handle_bot_usr_cmd_log(client: Client, userdata,  msg):
    """The function handles log command from Bot, so the Raspberry Pi log file name will be sent"""
    rp_id = int(msg.payload.decode())
    logging.info(f"Recieved\t| Bot send command {rp_id} log")
    client.publish(f"ice_runner/server/rp_commander/{rp_id}/command", "log")

@ServerMqttClient.client.topic_callback("ice_runner/bot/usr_cmd/state")
def handle_bot_usr_cmd_state(client: Client, userdata,  msg):
    """The function handles state messages from Bot to Raspberry Pi specified by id in message"""
    rp_id = int(msg.payload.decode())
    logging.info(f"Recieved\t| Bot send command {rp_id} state")
    client.publish("ice_runner/server/rp_commander/state", str(rp_id))

@ServerMqttClient.client.topic_callback("ice_runner/bot/usr_cmd/stop")
def handle_bot_usr_cmd_stop(client: Client, userdata,  msg):
    """The function handles stop messages from Bot to Raspberry Pi specified by id in message"""
    rp_id = int(msg.payload.decode())
    logging.info(f"Recieved\t| Bot send command {rp_id} stop")
    client.publish(f"ice_runner/server/rp_commander/{rp_id}/command", "stop")

@ServerMqttClient.client.topic_callback("ice_runner/bot/usr_cmd/start")
def handle_bot_usr_cmd_start(client: Client, userdata,  msg):
    """The function handles start messages from Bot to Raspberry Pi specified by id in message"""
    rp_id = int(msg.payload.decode())
    logging.info(f"Recieved\t| Bot send command {rp_id} start")
    client.publish(f"ice_runner/server/rp_commander/{rp_id}/command", "start")

@ServerMqttClient.client.topic_callback("ice_runner/bot/usr_cmd/status")
def handle_bot_usr_cmd_status(client: Client, userdata,  msg):
    """The function handles status messages from Bot to Raspberry Pi specified by id in message"""
    rp_id = int(msg.payload.decode())
    logging.info(f"Recieved\t| Bot send command {rp_id} status")
    client.publish(f"ice_runner/server/rp_commander/{rp_id}/command", "status")

@ServerMqttClient.client.topic_callback("ice_runner/bot/usr_cmd/who_alive")
def handle_bot_who_alive(client: Client, userdata,  msg):
    """The function sends who_alive message to all Raspberry Pis, so when a Raspberry Pi is connected, it will send state message to Bot"""
    logging.debug(f"Recieved\t| Bot send command who_alive")
    client.publish(f"ice_runner/server/rp_commander/who_alive", "who_alive")

@ServerMqttClient.client.topic_callback("ice_runner/bot/usr_cmd/config")
def handle_bot_config(client: Client, userdata,  msg):
    logging.debug(f"Recieved\t| Bot ask configuration")
    rp_id = int(msg.payload.decode())
    if rp_id not in ServerMqttClient.rp_configuration.keys():
        ServerMqttClient.rp_configuration[rp_id] = {}
        client.publish(f"ice_runner/server/rp_commander/{rp_id}/command", "config")
        return
    client.publish(f"ice_runner/bot_commander/rp_states/{rp_id}/config", str(ServerMqttClient.rp_configuration[rp_id]))
    ServerMqttClient.rp_configuration[rp_id] = None
    logging.debug(f"Published\t| Bot waiting for configuration of Raspberry Pi {rp_id}")

@ServerMqttClient.client.topic_callback("ice_runner/bot/usr_cmd/server")
def handle_bot_server(client: Client, userdata,  msg):
    """The function handles bot command /server"""
    logging.info(f"Recieved\t| Bot send command server")
    client.publish(f"ice_runner/server/bot_commander/server", "server")

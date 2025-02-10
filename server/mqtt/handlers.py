"""The module defines callbacks for the Server MQTT client"""

# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import logging
import yaml
from mqtt.client import ServerMqttClient
from paho.mqtt.client import Client
from common.RunnerState import safe_literal_eval

@ServerMqttClient.client.topic_callback("ice_runner/raspberry_pi/+/dronecan/#")
def handle_raspberry_pi_dronecan_message(client: Client, userdata,  msg):
    """The function handles dronecan messages from Raspberry Pi and stores them in dictionary"""
    del userdata, client
    rp_id = int(msg.topic.split("/")[2])
    message_type: str = msg.topic.split("/")[4]
    logging.debug("Published\t| Raspberry Pi %d send %s", rp_id, message_type)
    if rp_id not in ServerMqttClient.rp_messages:
        ServerMqttClient.rp_messages[rp_id] = {}
    ServerMqttClient.rp_messages[rp_id][message_type] = yaml.safe_load(msg.payload.decode())

@ServerMqttClient.client.topic_callback("ice_runner/raspberry_pi/+/status")
def handle_raspberry_pi_status(client: Client, userdata,  msg):
    """The function transmit status messages from Raspberry Pi to Bot"""
    del userdata
    rp_id = int(msg.topic.split("/")[2])
    logging.debug("Recieved\t| Raspberry Pi %d send status", rp_id)
    ServerMqttClient.rp_status[rp_id] = safe_literal_eval(msg.payload.decode())
    client.publish(f"ice_runner/server/bot_commander/rp_states/{rp_id}/status",
                   str(ServerMqttClient.rp_status[rp_id]))

@ServerMqttClient.client.topic_callback("ice_runner/raspberry_pi/+/state")
def handle_raspberry_pi_state(client: Client, userdata,  msg):
    """The function transmit state messages from Raspberry Pi to Bot"""
    del userdata
    rp_id = int(msg.topic.split("/")[2])
    logging.debug("Recieved\t| Raspberry Pi %d send state", rp_id)
    client.publish(f"ice_runner/server/bot_commander/rp_states/{rp_id}/state", msg.payload.decode())

@ServerMqttClient.client.topic_callback("ice_runner/raspberry_pi/+/config")
def handle_raspberry_pi_configuration(client: Client, userdata,  msg):
    """The function transmit configuration messages from Raspberry Pi to Bot"""
    del userdata
    rp_id = int(msg.topic.split("/")[2])
    logging.debug("Received\t| Raspberry Pi %d send configuration", rp_id)
    ServerMqttClient.rp_configuration[rp_id] = safe_literal_eval(msg.payload.decode())
    client.publish(f"ice_runner/server/bot_commander/rp_states/{rp_id}/config",
                   msg.payload.decode())

@ServerMqttClient.client.topic_callback("ice_runner/raspberry_pi/+/log")
def handle_raspberry_pi_log(client: Client, userdata,  msg):
    """The function handles log messages with log filename from Raspberry Pi to Bot.
        Can be used if bot is running on same machine. Otherwise, send the whole log file to Bot"""
    del userdata
    rp_id = int(msg.topic.split("/")[2])
    logging.info("Received\t| Raspberry Pi %d send log", rp_id)
    ServerMqttClient.rp_logs[rp_id] = msg.payload.decode()
    client.publish(f"ice_runner/server/bot_commander/rp_states/{rp_id}/log",
                   str(ServerMqttClient.rp_logs[rp_id]))

@ServerMqttClient.client.topic_callback("ice_runner/raspberry_pi/+/stop_reason")
def handle_raspberry_pi_stop_reason(client: Client, userdata,  msg):
    """The function transmit stop reason messages from Raspberry Pi to Bot"""
    del userdata
    rp_id = int(msg.topic.split("/")[2])
    logging.info("Received\t| Raspberry Pi %d send stop reason", rp_id)
    ServerMqttClient.rp_stop_reason[rp_id] = msg.payload.decode()
    client.publish(f"ice_runner/server/bot_commander/rp_states/{rp_id}/stop_reason",
                   ServerMqttClient.rp_stop_reason[rp_id])

@ServerMqttClient.client.topic_callback("ice_runner/bot/usr_cmd/log")
def handle_bot_usr_cmd_log(client: Client, userdata,  msg):
    """The function transmit log command from Bot, so the Raspberry Pi log file name will be sent"""
    del userdata
    rp_id = int(msg.payload.decode())
    logging.info("Recieved\t| Bot send command %d log", rp_id)
    client.publish(f"ice_runner/server/rp_commander/{rp_id}/command", "log")

@ServerMqttClient.client.topic_callback("ice_runner/bot/usr_cmd/state")
def handle_bot_usr_cmd_state(client: Client, userdata,  msg):
    """The function transmit state messages from Bot to Raspberry Pi specified by id in message"""
    del userdata
    rp_id = int(msg.payload.decode())
    logging.info("Recieved\t| Bot send command %d state", rp_id)
    client.publish("ice_runner/server/rp_commander/state", str(rp_id))

@ServerMqttClient.client.topic_callback("ice_runner/bot/usr_cmd/stop")
def handle_bot_usr_cmd_stop(client: Client, userdata,  msg):
    """The function transmit stop messages from Bot to Raspberry Pi specified by id in message"""
    del userdata
    rp_id = int(msg.payload.decode())
    logging.info("Recieved\t| Bot send command %d stop", rp_id)
    client.publish(f"ice_runner/server/rp_commander/{rp_id}/command", "stop")

@ServerMqttClient.client.topic_callback("ice_runner/bot/usr_cmd/start")
def handle_bot_usr_cmd_start(client: Client, userdata,  msg):
    """The function transmit start messages from Bot to Raspberry Pi specified by id in message"""
    del userdata
    rp_id = int(msg.payload.decode())
    logging.info("Recieved\t| Bot send command %d start", rp_id)
    client.publish(f"ice_runner/server/rp_commander/{rp_id}/command", "start")

@ServerMqttClient.client.topic_callback("ice_runner/bot/usr_cmd/status")
def handle_bot_usr_cmd_status(client: Client, userdata,  msg):
    """The function transmit status messages from Bot to Raspberry Pi specified by id in message"""
    del userdata
    rp_id = int(msg.payload.decode())
    logging.info("Recieved\t| Bot send command %d status", rp_id)
    client.publish(f"ice_runner/server/rp_commander/{rp_id}/command", "status")

@ServerMqttClient.client.topic_callback("ice_runner/bot/usr_cmd/who_alive")
def handle_bot_who_alive(client: Client, userdata,  msg):
    """The function sends who_alive message to all Raspberry Pis,
        so when a Raspberry Pi is connected, it will send state message to Bot"""
    del userdata, msg
    logging.debug("Recieved\t| Bot send command who_alive")
    client.publish(f"ice_runner/server/rp_commander/who_alive", "who_alive")

@ServerMqttClient.client.topic_callback("ice_runner/bot/usr_cmd/config")
def handle_bot_config(client: Client, userdata,  msg):
    """The function transmit bot command /config to Raspberry Pi"""
    del userdata
    rp_id = int(msg.payload.decode())
    logging.debug("Recieved\t| Bot ask configuration for %d", rp_id)
    if rp_id not in ServerMqttClient.rp_configuration:
        ServerMqttClient.rp_configuration[rp_id] = {}
        client.publish(f"ice_runner/server/rp_commander/{rp_id}/command", "config")
        return
    client.publish(f"ice_runner/bot_commander/rp_states/{rp_id}/config",
                   str(ServerMqttClient.rp_configuration[rp_id]))
    ServerMqttClient.rp_configuration[rp_id] = None
    logging.debug("Published\t| Bot waiting for configuration of Raspberry Pi %d", rp_id)

@ServerMqttClient.client.topic_callback("ice_runner/bot/usr_cmd/server")
def handle_bot_server(client: Client, userdata,  msg):
    """The function handles bot command /server"""
    del userdata, msg
    logging.info("Recieved\t| Bot send command server")
    client.publish(f"ice_runner/server/bot_commander/server", "server")

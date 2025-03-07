"""The module defines callbacks for the Server MQTT client"""

# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import json
import logging

from server.mqtt.client import ServerMqttClient
from paho.mqtt.client import Client


@ServerMqttClient.client.topic_callback("ice_runner/raspberry_pi/+/dronecan/#")
def handle_raspberry_pi_dronecan_message(client: Client, userdata,  msg):
    """The function handles dronecan messages from Raspberry Pi and stores them in dictionary"""
    del userdata, client
    rp_id = int(msg.topic.split("/")[2])
    message_type: str = msg.topic.split("/")[4]
    logging.debug("Published\t| Raspberry Pi %d %s", rp_id, message_type)
    if rp_id not in ServerMqttClient.rp_messages:
        ServerMqttClient.rp_messages[rp_id] = {}
    ServerMqttClient.rp_messages[rp_id][message_type] = json.loads(msg.payload.decode())

@ServerMqttClient.client.topic_callback("ice_runner/raspberry_pi/+/status")
def handle_raspberry_pi_status(client: Client, userdata,  msg):
    """The function transmit status messages from Raspberry Pi to Bot"""
    del userdata
    rp_id = int(msg.topic.split("/")[2])
    logging.debug("Recieved\t| Raspberry Pi %d status", rp_id)
    ServerMqttClient.rp_status[rp_id] = json.loads(msg.payload.decode())
    client.publish(f"ice_runner/server/bot_commander/rp_states/{rp_id}/status",
                   json.dumps(ServerMqttClient.rp_status[rp_id]))

@ServerMqttClient.client.topic_callback("ice_runner/raspberry_pi/+/state")
def handle_raspberry_pi_state(client: Client, userdata,  msg):
    """The function transmit state messages from Raspberry Pi to Bot"""
    del userdata
    rp_id = int(msg.topic.split("/")[2])
    logging.debug("Recieved\t| Raspberry Pi %d state", rp_id)
    client.publish(f"ice_runner/server/bot_commander/rp_states/{rp_id}/state", msg.payload.decode())

@ServerMqttClient.client.topic_callback("ice_runner/raspberry_pi/+/config")
def handle_raspberry_pi_configuration(client: Client, userdata,  msg):
    """The function transmit configuration messages from Raspberry Pi to Bot"""
    del userdata
    config = (msg.payload.decode())
    rp_id = int(msg.topic.split("/")[2])
    logging.info("Received\t| Raspberry Pi %d configuration", rp_id)
    ServerMqttClient.rp_configuration[rp_id] = config
    client.publish(f"ice_runner/server/bot_commander/rp_states/{rp_id}/config", config)

@ServerMqttClient.client.topic_callback("ice_runner/raspberry_pi/+/full_config")
def handle_raspberry_pi_full_config(client: Client, userdata,  msg):
    """The function transmit full configuration messages from Raspberry Pi to Bot"""
    del userdata
    rp_id = int(msg.topic.split("/")[2])
    config = (msg.payload.decode())
    logging.info("Received\t| Raspberry Pi %d full configuration", rp_id)
    ServerMqttClient.rp_full_configuration[rp_id] = config
    client.publish(f"ice_runner/server/bot_commander/rp_states/{rp_id}/full_config", config)

@ServerMqttClient.client.topic_callback("ice_runner/raspberry_pi/+/log")
def handle_raspberry_pi_log(client: Client, userdata,  msg):
    """The function handles log messages with log filename from Raspberry Pi to Bot.
        Can be used if bot is running on same machine. Otherwise, send the whole log file to Bot"""
    del userdata
    rp_id = int(msg.topic.split("/")[2])
    logging.info("Received\t| Raspberry Pi %d log", rp_id)
    ServerMqttClient.rp_logs[rp_id] = msg.payload.decode()
    client.publish(f"ice_runner/server/bot_commander/rp_states/{rp_id}/log",
                   msg.payload.decode())

@ServerMqttClient.client.topic_callback("ice_runner/raspberry_pi/+/stop_reason")
def handle_raspberry_pi_stop_reason(client: Client, userdata,  msg):
    """The function transmit stop reason messages from Raspberry Pi to Bot"""
    del userdata
    rp_id = int(msg.topic.split("/")[2])
    logging.info("Received\t| Raspberry Pi %d stop reason", rp_id)
    ServerMqttClient.rp_stop_reason[rp_id] = msg.payload.decode()
    client.publish(f"ice_runner/server/bot_commander/rp_states/{rp_id}/stop_reason",
                   msg.payload.decode())

@ServerMqttClient.client.topic_callback("ice_runner/bot/usr_cmd/log")
def handle_bot_usr_cmd_log(client: Client, userdata,  msg):
    """The function transmit log command from Bot, so the Raspberry Pi log file name will be sent"""
    del userdata
    rp_id = int(msg.payload.decode())
    logging.info("Recieved\t| Bot command %d log", rp_id)
    client.publish(f"ice_runner/server/rp_commander/{rp_id}/command", "log")

@ServerMqttClient.client.topic_callback("ice_runner/bot/usr_cmd/state")
def handle_bot_usr_cmd_state(client: Client, userdata,  msg):
    """The function transmit state messages from Bot to Raspberry Pi specified by id in message"""
    del userdata
    rp_id = int(msg.payload.decode())
    logging.info("Recieved\t| Bot command %d state", rp_id)
    client.publish("ice_runner/server/rp_commander/state", str(rp_id))

@ServerMqttClient.client.topic_callback("ice_runner/bot/usr_cmd/stop")
def handle_bot_usr_cmd_stop(client: Client, userdata,  msg):
    """The function transmit stop messages from Bot to Raspberry Pi specified by id in message"""
    del userdata
    rp_id = int(msg.payload.decode())
    logging.info("Recieved\t| Bot command %d stop", rp_id)
    client.publish(f"ice_runner/server/rp_commander/{rp_id}/command", "stop")

@ServerMqttClient.client.topic_callback("ice_runner/bot/usr_cmd/start")
def handle_bot_usr_cmd_start(client: Client, userdata,  msg):
    """The function transmit start messages from Bot to Raspberry Pi specified by id in message"""
    del userdata
    rp_id = int(msg.payload.decode())
    logging.info("Recieved\t| Bot command %d start", rp_id)
    client.publish(f"ice_runner/server/rp_commander/{rp_id}/command", "start")

@ServerMqttClient.client.topic_callback("ice_runner/bot/usr_cmd/status")
def handle_bot_usr_cmd_status(client: Client, userdata,  msg):
    """The function transmit status messages from Bot to Raspberry Pi specified by id in message"""
    del userdata
    rp_id = int(msg.payload.decode())
    logging.info("Recieved\t| Bot command %d status", rp_id)
    client.publish(f"ice_runner/server/rp_commander/{rp_id}/command", "status")

@ServerMqttClient.client.topic_callback("ice_runner/bot/usr_cmd/who_alive")
def handle_bot_who_alive(client: Client, userdata,  msg):
    """The function sends who_alive message to all Raspberry Pis,
        so when a Raspberry Pi is connected, it will send state message to Bot"""
    del userdata, msg
    logging.debug("Recieved\t| Bot command who_alive")
    client.publish("ice_runner/server/rp_commander/who_alive", "who_alive")

@ServerMqttClient.client.topic_callback("ice_runner/bot/usr_cmd/config")
def handle_bot_config(client: Client, userdata,  msg):
    """The function transmit bot command /config to Raspberry Pi"""
    del userdata
    rp_id = int(msg.payload.decode())
    logging.info("Recieved\t| Bot command configuration for %d", rp_id)
    client.publish(f"ice_runner/server/rp_commander/{rp_id}/command", "config")

@ServerMqttClient.client.topic_callback("ice_runner/bot/usr_cmd/+/change_config/#")
def handle_bot_change_config(client: Client, userdata,  msg):
    """The function handles bot command /config"""
    del userdata
    rp_id = msg.topic.split("/")[-3]
    param_name = msg.topic.split("/")[-1]
    logging.info("Received\t| New config %s value cmd for Raspberry Pi %s", param_name, rp_id)
    client.publish(f"ice_runner/server/rp_commander/{rp_id}/change_config/{param_name}",
                   msg.payload.decode())

@ServerMqttClient.client.topic_callback("ice_runner/bot/usr_cmd/full_config")
def handle_bot_full_config(client: Client, userdata,  msg):
    """The function handles bot command /config"""
    del userdata
    rp_id = int(msg.payload.decode())
    client.publish(f"ice_runner/server/rp_commander/{rp_id}/command",
                   "full_config")
    logging.info("Received\t| Full config cmd for Raspberry Pi %d", rp_id)

@ServerMqttClient.client.topic_callback("ice_runner/bot/usr_cmd/server")
def handle_bot_server(client: Client, userdata,  msg):
    """The function handles bot command /server"""
    del userdata, msg
    logging.info("Recieved\t| Bot command server")
    client.publish("ice_runner/server/bot_commander/server", "server")

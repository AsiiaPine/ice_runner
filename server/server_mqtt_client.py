import math
import os
import sys
import time
from typing import Any, Dict
import yaml
from paho import mqtt
from paho.mqtt.client import MQTTv311, Client
import ast
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from common.RPStates import RPStates, safe_literal_eval
from common.IceRunnerConfiguration import IceRunnerConfiguration
import logging
import logging_configurator
logger = logging_configurator.AsyncLogger(__name__)

class ServerMqttClient:
    client = Client(client_id="server", clean_session=True, userdata=None, protocol=MQTTv311, reconnect_on_failure=True)
    rp_messages: Dict[int, Dict[str, Dict[str, Any]]] = {}
    rp_status: Dict[int, Any] = {}
    rp_setpoint: Dict[int, float] = {}
    rp_cur_setpoint: Dict[int, float] = {}

    last_ready_transmit = 0
    rp_configuration: Dict[int, IceRunnerConfiguration] = {}

    @classmethod
    def connect(cls, server_ip: str = "localhost", port: int = 1883) -> None:
        cls.client = Client(client_id="server", clean_session=True, userdata=None, protocol=MQTTv311, reconnect_on_failure=True)
        cls.client.connect(server_ip, port, 60)
        cls.client.publish("ice_runner/server/raspberry_pi_commander", "ready")
        cls.client.publish("ice_runner/server/bot_commander", "ready")
        logger.info("started server")

    @classmethod
    def get_client(cls) -> mqtt.client.Client:
        return cls.client

    @classmethod
    def publish_rp_state(cls, rp_id: int) -> None:
        if rp_id not in cls.rp_status.keys():
            logger.info(f"Published\t| Raspberry Pi {rp_id} is not connected ")
            return
        if cls.rp_status[rp_id] is None:
            logger.info(f"Published\t|Raspberry Pi {rp_id} no state set")
            return
        cls.client.publish(f"ice_runner/server/bot_commander/rp_states/{rp_id}/state", cls.rp_status[rp_id]["state"])

    @classmethod
    def publish_rp_status(cls, rp_id: int) -> None:
        if rp_id not in cls.rp_status.keys():
            logger.info(f"Published\t| Raspberry Pi is not connected")
            return
        status = cls.rp_status[rp_id]
        cls.client.publish(f"ice_runner/server/bot_commander/rp_states/{rp_id}/status", str(status))

    @classmethod
    def publish_rp_states(cls) -> None:
        for rp_id, status in cls.rp_status.items():
            cls.publish_rp_state(rp_id)
            cls.publish_rp_status(rp_id)

def handle_raspberry_pi_dronecan_message(client, userdata, msg):
    rp_id = int(msg.topic.split("/")[2])
    message_type: str = msg.topic.split("/")[4]
    logger.info(f"Published\t| Raspberry Pi {rp_id} send {message_type}")
    if rp_id not in ServerMqttClient.rp_messages.keys():
        ServerMqttClient.rp_messages[rp_id] = {}
    if message_type not in ServerMqttClient.rp_messages[rp_id].keys():
        ServerMqttClient.rp_messages[rp_id][message_type] = {}
    ServerMqttClient.rp_messages[rp_id][message_type] = yaml.safe_load(msg.payload.decode())

def handle_raspberry_pi_status(client, userdata, msg):
    rp_id = int(msg.topic.split("/")[2])
    logging.info(f"Recieved\t| Raspberry Pi {rp_id} send status")
    ServerMqttClient.rp_status[rp_id] = safe_literal_eval(msg.payload.decode())
    ServerMqttClient.client.publish(f"ice_runner/server/bot_commander/rp_states/{rp_id}/state", ServerMqttClient.rp_status[rp_id]["state"])
    ServerMqttClient.client.publish(f"ice_runner/server/bot_commander/rp_states/{rp_id}/status", str(ServerMqttClient.rp_status[rp_id]))
    ServerMqttClient.rp_status[rp_id] = None

def handle_raspberry_pi_configuration(client, userdata, msg):
    rp_id = int(msg.topic.split("/")[2])
    logging.info(f"Received\t| Raspberry Pi {rp_id} send configuration")
    ServerMqttClient.rp_configuration[rp_id] = safe_literal_eval(msg.payload.decode())
    ServerMqttClient.client.publish(f"ice_runner/server/bot_commander/rp_states/{rp_id}/config", str(ServerMqttClient.rp_configuration[rp_id]))
    print(f"Published\t| Bot received configuration for Raspberry Pi")

def handle_bot_usr_cmd_state(client, userdata,  msg):
    # print("got bot usr cmd state")
    rp_id = int(msg.payload.decode())
    logger.info(f"Recieved\t| Bot send command {rp_id} get_conf")
    ServerMqttClient.client.publish("ice_runner/server/rp_commander/get_conf", str(rp_id))

def handle_bot_usr_cmd_stop(client, userdata,  msg):
    rp_id = int(msg.payload.decode())
    logger.info(f"Recieved\t| Bot send command {rp_id} stop")
    ServerMqttClient.client.publish(f"ice_runner/server/bot_commander/{rp_id}/command", "stop")
    ServerMqttClient.rp_setpoint[rp_id] = 0
    ServerMqttClient.client.publish(f"ice_runner/server/bot_commander/{rp_id}/setpoint", 0)
    while True:
        if ServerMqttClient.rp_status[rp_id] is None:
            logger.info(f"STATUS\t| Raspberry Pi {rp_id} did not send its status")
            time.sleep(0.1)
            continue
        if ServerMqttClient.rp_status[rp_id].state != RPStates.RUNNING.value:
            time.sleep(0.1)
            ServerMqttClient.publish_rp_state(rp_id)
            break
        logging.info(f"Raspberry Pi {rp_id} is stopping. Current state: {ServerMqttClient.rp_status[rp_id].state}")
        time.sleep(0.1)

def handle_bot_usr_cmd_start(client, userdata,  msg):
    rp_id = int(msg.payload.decode())
    ServerMqttClient.client.publish(f"ice_runner/server/rp_commander/{rp_id}/command", "start")
    ServerMqttClient.client.publish(f"ice_runner/server/bot_commander/{rp_id}/setpoint", 8191)
    ServerMqttClient.rp_setpoint[rp_id] = 8191

def handle_bot_configure(client, userdata, msg):
    rp_id = int(msg.topic.split("/")[-1])
    if rp_id not in ServerMqttClient.rp_configuration.keys():
        ServerMqttClient.rp_configuration[rp_id] = {}
    cofig = ast.literal_eval(msg.payload.decode())
    for name, value in cofig.items():
        ServerMqttClient.rp_configuration[rp_id][name] = value

def handle_bot_config(client, userdata, msg):
    logger.info(f"Recieved\t| Bot send configuration")
    rp_id = int(msg.payload.decode())
    if rp_id not in ServerMqttClient.rp_configuration.keys():
        ServerMqttClient.rp_configuration[rp_id] = {}
    ServerMqttClient.client.publish(f"ice_runner/server/rp_commander/config", str(rp_id))
    logger.info(f"Published\t| Bot waiting for configuration for Raspberry Pi {rp_id}")

def start() -> None:
    ServerMqttClient.client.message_callback_add("ice_runner/raspberry_pi/+/status", handle_raspberry_pi_status)
    ServerMqttClient.client.message_callback_add("ice_runner/raspberry_pi/+/dronecan/#", handle_raspberry_pi_dronecan_message)

    ServerMqttClient.client.message_callback_add("ice_runner/raspberry_pi/+/configuration", handle_raspberry_pi_configuration)

    ServerMqttClient.client.message_callback_add("ice_runner/bot/usr_cmd/state", handle_bot_usr_cmd_state)
    ServerMqttClient.client.message_callback_add("ice_runner/bot/usr_cmd/stop", handle_bot_usr_cmd_stop)
    ServerMqttClient.client.message_callback_add("ice_runner/bot/usr_cmd/start", handle_bot_usr_cmd_start)
    ServerMqttClient.client.message_callback_add("ice_runner/bot/usr_cmd/config", handle_bot_config)
    ServerMqttClient.client.message_callback_add("ice_runner/bot/configure/#", handle_bot_configure)
    ServerMqttClient.client.subscribe("ice_runner/raspberry_pi/#")
    ServerMqttClient.client.subscribe("ice_runner/bot/#")
    ServerMqttClient.client.loop_start()

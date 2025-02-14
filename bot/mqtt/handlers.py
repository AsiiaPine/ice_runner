"""The module defines callbacks for the Bot MQTT client"""

# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import logging
from mqtt.client import MqttClient
from telegram.scheduler import Scheduler
from common.RunnerState import RunnerState
from common.algorithms import safe_literal_eval

@MqttClient.client.topic_callback("ice_runner/server/bot_commander/rp_states/+/state")
def handle_commander_state(client, userdata, message):
    """The function handles state messages from Raspberry Pi to Bot mqtt client storage"""
    del client, userdata
    rp_pi_id = int(message.topic.split("/")[-2])
    if rp_pi_id not in Scheduler.jobs:
        Scheduler.guard_runner(rp_pi_id)
        print("GUARDING\t| RP %d", rp_pi_id)
    state = RunnerState(int(message.payload.decode()))
    MqttClient.rp_states[rp_pi_id] = state
    logging.debug("received RP state from Raspberry Pi %d, state: %s", rp_pi_id, state.name)

@MqttClient.client.topic_callback("ice_runner/server/bot_commander/rp_states/+/status")
def handle_commander_status(client, userdata, message):
    """The function stores status from Raspberry Pi to Bot mqtt client storage"""
    del client, userdata
    rp_pi_id = int(message.topic.split("/")[-2])
    status = safe_literal_eval(message.payload.decode())
    if status is not None:
        MqttClient.rp_status[rp_pi_id] = status
        logging.debug("received RP status from Raspberry Pi %d", rp_pi_id)

@MqttClient.client.topic_callback("ice_runner/server/bot_commander/rp_states/+/config")
def handle_commander_config(client, userdata, message):
    """The function stores configuration from Raspberry Pi to Bot mqtt client storage"""
    del client, userdata
    rp_pi_id = int(message.topic.split("/")[-2])
    MqttClient.rp_configuration[rp_pi_id] = safe_literal_eval(message.payload.decode())
    logging.debug("received RP configuration from Raspberry Pi %d", rp_pi_id)

@MqttClient.client.topic_callback("ice_runner/server/bot_commander/server")
def handle_commander_server(client, userdata, message):
    """The function handles server callback used to check connection"""
    del client, userdata, message
    MqttClient.server_connected = True
    logging.debug("received SERVER connection from Raspberry Pi")

@MqttClient.client.topic_callback("ice_runner/server/bot_commander/rp_states/+/log")
def handle_commander_log(client, userdata, message):
    """The function stores logs from Raspberry Pi to Bot mqtt client storage"""
    del client, userdata
    rp_pi_id = int(message.topic.split("/")[-2])
    MqttClient.rp_logs[rp_pi_id] = safe_literal_eval(message.payload.decode())
    logging.info("received LOG from Raspberry Pi %d", rp_pi_id)

@MqttClient.client.topic_callback("ice_runner/server/bot_commander/rp_states/+/stop_reason")
def handle_commander_stop_handlers(client, userdata, message):
    """The function stores stop reason from Raspberry Pi to Bot mqtt client storage"""
    del client, userdata
    rp_pi_id = int(message.topic.split("/")[-2])
    logging.info("received STOP_REASON from Raspberry Pi %d %s", rp_pi_id, message.payload.decode())
    MqttClient.rp_stop_handlers[rp_pi_id] = message.payload.decode()

@MqttClient.client.topic_callback("ice_runner/server/bot_commander/rp_states/+/full_config")
def handle_commander_full_config(client, userdata, message):
    """The function stores full configuration from Raspberry Pi to Bot mqtt client storage"""
    del client, userdata
    rp_pi_id = int(message.topic.split("/")[-2])
    logging.info("received FULL_CONFIG from Raspberry Pi %d %s", rp_pi_id, message.payload.decode())
    MqttClient.runner_full_configuration[rp_pi_id] = safe_literal_eval(message.payload.decode())

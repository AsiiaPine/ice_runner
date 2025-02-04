#!/usr/bin/env python3
# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

from mqtt.client import MqttClient
from paho.mqtt.client import Client
from common.RPStates import safe_literal_eval, RunnerState
import logging

def handle_commander_state(client, userdata, message):
    rp_pi_id = int(message.topic.split("/")[-2])
    if rp_pi_id not in MqttClient.rp_states.keys():
        MqttClient.rp_states[rp_pi_id] = RunnerState.NOT_CONNECTED
    state = RunnerState(int(message.payload.decode()))
    MqttClient.rp_states[rp_pi_id] = state
    logging.getLogger(__name__).debug(f"received RP state from Raspberry Pi {rp_pi_id}, state: {state.name}")

def handle_commander_status(client, userdata, message):
    rp_pi_id = int(message.topic.split("/")[-2])
    status = safe_literal_eval(message.payload.decode())
    if status is not None:
        MqttClient.rp_status[rp_pi_id] = status
        logging.getLogger(__name__).debug(f"received RP status from Raspberry Pi {rp_pi_id}")

def handle_commander_config(client, userdata, message):
    rp_pi_id = int(message.topic.split("/")[-2])
    MqttClient.rp_configuration[rp_pi_id] = safe_literal_eval(message.payload.decode())
    logging.getLogger(__name__).debug(f"received RP configuration from Raspberry Pi {rp_pi_id}")

def handle_commander_server(client, userdata, message):
    MqttClient.server_connected = True
    logging.getLogger(__name__).debug(f"received SERVER connection from Raspberry Pi")

def handle_commander_log(client, userdata, message):
    rp_pi_id = int(message.topic.split("/")[-2])
    logging.getLogger(__name__).debug(f"received LOG from Raspberry Pi {message.payload.decode()}")
    MqttClient.rp_logs[rp_pi_id] = safe_literal_eval(message.payload.decode())
    logging.getLogger(__name__).debug(f"received LOG from Raspberry Pi {rp_pi_id}")

def add_handlers(client: Client) -> None:
    client.message_callback_add("ice_runner/server/bot_commander/rp_states/+/state", handle_commander_state)
    client.message_callback_add("ice_runner/server/bot_commander/rp_states/+/status", handle_commander_status)
    client.message_callback_add("ice_runner/server/bot_commander/rp_states/+/config", handle_commander_config)
    client.message_callback_add("ice_runner/server/bot_commander/rp_states/+/log", handle_commander_log)
    client.message_callback_add("ice_runner/server/bot_commander/server", handle_commander_server)

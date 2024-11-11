import ast
import os
import sys
import time
from typing import Any, Dict, List
from paho import mqtt
from paho.mqtt.client import MQTTv311
import yaml
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from common.IceRunnerConfiguration import IceRunnerConfiguration
from dronecan_communication.DronecanMessages import Message
from common.RPStates import RPStates
# from dronecan_commander import DronecanCommander

class RaspberryMqttClient:
    client = mqtt.client.Client(client_id="raspberry_0", clean_session=True, userdata=None, protocol=MQTTv311)
    rp_id: int = 0
    last_message_receive_time = 0
    setpoint_command: float = 0
    to_run: bool = 0
    to_stop: bool = 0
    state = RPStates.WAITING
    configuration: IceRunnerConfiguration
    # = IceRunnerConfiguration.from_dict({})

    @classmethod
    def get_client(cls) -> mqtt.client.Client:
        return cls.client

    @classmethod
    def connect(cls, rp_id: int, server_ip: str, port: int = 1883, max_messages: int = 2) -> None:
        cls.is_connected = False
        cls.rp_id = rp_id
        cls.client = mqtt.client.Client(client_id=f"raspberry_{rp_id}", clean_session=True, protocol=MQTTv311, reconnect_on_failure=True)
        cls.client.connect(server_ip, port, 60)
        cls.client.publish(f"ice_runner/raspberry_pi/{rp_id}/state", RPStates.WAITING.value)
        print(f"ice_runner/raspberry_pi/{rp_id}/state")

    @classmethod
    def set_id(cls, rp_id: str) -> None:
        cls.rp_id = rp_id
        cls.client._client_id = f"raspberry_{rp_id}"

    @classmethod
    def publish_messages(cls, state: Dict[str, Dict[str, Message]]) -> None:
        for dronecan_type in state.keys():
            cls.client.publish(f"ice_runner/raspberry_pi/{cls.rp_id}/dronecan/{dronecan_type}", str(state[dronecan_type].to_dict()))
        # cls.client.publish(f"ice_runner/raspberry_pi/{cls.rp_id}/state", cls.state.value)
        # cls.client.publish(f"ice_runner/raspberry_pi/{cls.rp_id}/setpoint", cls.setpoint_command)

    @classmethod
    def publish_state(cls, state: Dict[str, Any]) -> None:
        cls.client.publish(f"ice_runner/raspberry_pi/{cls.rp_id}/stats", str(state))
        cls.client.publish(f"ice_runner/raspberry_pi/{cls.rp_id}/state", state["state"])

def handle_command(client, userdata, message):
    print(f"RP:\t{message.topic}: {message.payload.decode()}")
    mes_text = message.payload.decode()
    if mes_text == "start":
        print("RP:\tStart")
        RaspberryMqttClient.state = RPStates.STARTING
        RaspberryMqttClient.to_run = 1
        # DronecanCommander.to_run = 1
    if mes_text == "stop":
        print("RP:\tStop")
        RaspberryMqttClient.state = RPStates.STOPPING
        RaspberryMqttClient.to_stop = 1
        # DronecanCommander.to_run = 0

    if mes_text == "run":
        if RaspberryMqttClient.state < RPStates.STARTING:
            print("RP:\tCall Start first")
        else:
            print("RP:\tRun")
    if mes_text == "keep alive":
        RaspberryMqttClient.last_message_receive_time = time.time()

    if mes_text == "status":
        RaspberryMqttClient.publish_state(RaspberryMqttClient.state)

def handle_configuration(client, userdata, message):
    print("RP:\tConfiguration")
    rp_id = int(message.payload.decode())
    if rp_id == RaspberryMqttClient.rp_id:
        RaspberryMqttClient.client.publish(f"ice_runner/raspberry_pi/{RaspberryMqttClient.rp_id}/configuration", str(RaspberryMqttClient.configuration.to_dict()))

def handle_config(client, userdata, message):
    print("RaspberryPi:\tConfiguration")
    print("RaspberryMqttClient.configuration.to_dict()")
    RaspberryMqttClient.client.publish(f"ice_runner/raspberry_pi/{RaspberryMqttClient.rp_id}/configuration", str(RaspberryMqttClient.configuration.to_dict()))
    # rp_id = int(message.payload.decode())


def start() -> None:
    RaspberryMqttClient.client.message_callback_add(f"ice_runner/server/rp_commander/{RaspberryMqttClient.rp_id}/command", handle_command)

    RaspberryMqttClient.client.message_callback_add(f"ice_runner/server/rp_commander/config", handle_config)

    # RaspberryMqttClient.client.message_callback_add(f"ice_runner/server/raspberry_pi_commander/{RaspberryMqttClient.rp_id}/setpoint", handle_setpoint)

    RaspberryMqttClient.client.subscribe(f"ice_runner/server/rp_commander/{RaspberryMqttClient.rp_id}/#")
    RaspberryMqttClient.client.subscribe(f"ice_runner/server/rp_commander/#")
    RaspberryMqttClient.client.loop_start()

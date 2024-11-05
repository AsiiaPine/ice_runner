import os
import sys
import time
from typing import Any, Dict, List
from paho import mqtt
from paho.mqtt.client import MQTTv311
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from common.RPStates import RPStates

class RaspberryMqttClient:
    client = mqtt.client.Client(client_id="raspberry_0", clean_session=True, userdata=None, protocol=MQTTv311)
    rp_id: int = 0
    last_message_receive_time = 0
    setpoint_command: float = 0
    nodes_states: Dict[str, List[str]] = {}
    state = RPStates.WAITING

    @classmethod
    def get_client(cls) -> mqtt.client.Client:
        return cls.client

    @classmethod
    def connect(cls, rp_id: int, server_ip: str, port: int = 1883, max_messages: int = 2) -> None:
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
    def publish_state(cls, state: Dict[str, Dict[str, Any]]) -> None:
        print("publishing state")
        for node_type in state.keys():
            print(f"Publishing {node_type} state")
            for dronecan_type in state[node_type].keys():
                cls.client.publish(f"ice_runner/raspberry_pi/{cls.rp_id}/dronecan/{dronecan_type}", str(state[node_type][dronecan_type]))
        cls.client.publish(f"ice_runner/raspberry_pi/{cls.rp_id}/state", RaspberryMqttClient.state.value)
        cls.client.publish(f"ice_runner/raspberry_pi/{cls.rp_id}/command", RaspberryMqttClient.setpoint_command)

def handle_command(client, userdata, message):
    print(f"RP:\t{message.topic}: {message.payload.decode()}")
    mes_text = message.payload.decode()
    if mes_text == "start":
        print("RP:\tStart")
        RaspberryMqttClient.state = RPStates.STARTING
    if mes_text == "stop":
        print("RP:\tStop")
        RaspberryMqttClient.state = RPStates.STOPPING
        RaspberryMqttClient.setpoint_command = 0

    if mes_text == "run":
        if RaspberryMqttClient.state < RPStates.STARTING:
            print("RP:\tCall Start first")
        else:
            print("RP:\tRun")
    if message.payload.decode() == "keep alive":
        print("RP:\tKeep alive")
        RaspberryMqttClient.last_message_receive_time = time.time()

def handle_setpoint(client, userdata, message):
    print(f"RP:\t{message.topic}: {message.payload.decode()}")
    RaspberryMqttClient.setpoint_command = float(message.payload.decode())

def handle_config(client, userdata, message):
    print("RP:\tConfiguration")

def start() -> None:
    RaspberryMqttClient.client.message_callback_add(f"ice_runner/server/raspberry_pi_commander/{RaspberryMqttClient.rp_id}/command", handle_command)

    RaspberryMqttClient.client.message_callback_add(f"ice_runner/server/raspberry_pi_commander/{RaspberryMqttClient.rp_id}/config", handle_config)

    RaspberryMqttClient.client.subscribe(f"ice_runner/server/raspberry_pi_commander/{RaspberryMqttClient.rp_id}/#")
    RaspberryMqttClient.client.loop_start()

from enum import IntEnum
import time
from typing import Any, Dict, List
import paho.mqtt.client as paho
from paho import mqtt
from paho.mqtt.client import MQTTv311

# TODO: specify callbacks for each topic with
# @client.topic_callback("mytopic/#")
# def handle_mytopic(client, userdata, message):
class RPStates(IntEnum):
    READY       = 0
    STOPPING    = 1
    STOPPED     = 2
    STARTING    = 3
    RUNNING     = 4


class RaspberryMqttClient:
    client = mqtt.client.Client(client_id="raspberry_0", clean_session=True, userdata=None, protocol=MQTTv311)
    rp_id: int = 0
    setpoint_command: float = 0
    nodes_states: Dict[str, List[str]] = {}
    state = RPStates.READY

    @classmethod
    def get_client(cls) -> mqtt.client.Client:
        return cls.client

    @classmethod
    def connect(cls, rp_id: int, server_ip: str, port: int = 1883, max_messages: int = 2) -> None:
        cls.rp_id = rp_id
        cls.client = mqtt.client.Client(client_id=f"raspberry_{rp_id}", clean_session=True, protocol=MQTTv311, reconnect_on_failure=True)
        cls.client.connect(server_ip, port, 60)
        cls.client.subscribe(f"ice_runner/server/rp_commander/{rp_id}/#")
        cls.client.publish(f"ice_runner/raspberry_pi/{rp_id}/state", "ready")
        cls.client.loop_start()

    @classmethod
    def set_id(cls, rp_id: str) -> None:
        cls.rp_id = rp_id
        cls.client._client_id = f"raspberry_{rp_id}"

    @classmethod
    def loop_forever(cls) -> None:
        try:
            print("RP:\tPress CTRL+C to exit")
            cls.client.loop_forever()
        except:
            print("RP:\tExiting...")

    @classmethod
    def publich_state(cls, state: Dict[str, Dict[str, Any]]) -> None:
        for node_type in state.keys():
            for dronecan_type in state[node_type].keys():
                cls.client.publish(f"ice_runner/raspberry_pi/{cls.rp_id}/{node_type}/{dronecan_type}", str(state[node_type][dronecan_type]))
        cls.client.publish(f"ice_runner/raspberry_pi/{cls.rp_id}/state", RaspberryMqttClient.state.value)

@RaspberryMqttClient.client.topic_callback("ice_runner/server/rp_commander/{rp_id}/command")
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

@RaspberryMqttClient.client.topic_callback("ice_runner/raspberry_pi/{rp_id}/setpoint")
def handle_setpoint(client, userdata, message):
    print(f"RP:\t{message.topic}: {message.payload.decode()}")
    RaspberryMqttClient.setpoint_command = float(message.payload.decode())


@classmethod
@RaspberryMqttClient.client.topic_callback("ice_runner/raspberry_pi/{rp_id}/conf")
def handle_conf(client, userdata, message):
    print("RP:\tConfiguration")

RaspberryMqttClient.client.message_callback_add("ice_runner/server/rp_commander/{rp_id}/command", handle_command)
RaspberryMqttClient.client.message_callback_add("ice_runner/raspberry_pi/{rp_id}/conf", handle_conf)

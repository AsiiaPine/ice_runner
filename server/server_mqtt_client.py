import os
import sys
import time
from typing import Any, Dict
import yaml
from paho import mqtt
from paho.mqtt.client import MQTTv311, Client
import ast
import pprint
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from common.RPStates import RPStates

class RPStatus:
    def __init__(self, id: int, state: int = None) -> None:
        self.id: int = id
        self.state: int = state
        self.rpm: int = None
        self.temperature: int = None
        self.available_fuel_volume: float = None

        self.voltage_out: float = None
        self.current: float = None
        self.external_temperature: float = None
        self.gas_throttle: int = None
        self.air_throttle: int = None

        self.vibrations: int = None
        self.engaged_time: int = None

    def to_yaml_str(self) -> str:
        # string = yaml.dump(self, default_flow_style=False)
        yaml.emitter.Emitter.prepare_tag = lambda self, tag: ''
        return yaml.dump(self, default_flow_style=False)

    def update_with_resiprocating_status(self, status: Dict[str, Any]) -> None:
        self.state = status["state"]
        self.rpm = status["engine_speed_rpm"]
        self.gas_throttle = status["engine_load_percent"]
        self.air_throttle = status["throttle_position_percent"]
        self.temperature = status["oil_temperature"]
        self.current = status["intake_manifold_temperature"]
        self.voltage_out = status["fuel_pressure"]

    def update_with_raw_imu(self, status: Dict[str, Any]) -> None:
        self.vibrations = status["integration_interval"]

class ServerMqttClient:
    client = Client(client_id="server", clean_session=True, userdata=None, protocol=MQTTv311, reconnect_on_failure=True)
    rp_messages: Dict[int, Dict[str, Dict[str, Any]]] = {}
    rp_status: Dict[int, RPStatus] = {}
    rp_cmd: Dict[int, float] = {}
    last_ready_transmit = 0

    @classmethod
    def connect(cls, server_ip: str = "localhost", port: int = 1883) -> None:
        cls.client = Client(client_id="server", clean_session=True, userdata=None, protocol=MQTTv311, reconnect_on_failure=True)
        cls.client.connect(server_ip, port, 60)
        cls.client.publish("ice_runner/server/raspberry_pi_commander", "ready")
        cls.client.publish("ice_runner/server/bot_commander", "ready")
        print("started server")

    @classmethod
    def get_client(cls) -> mqtt.client.Client:
        return cls.client

    @classmethod
    def analyse_rp_messages(cls, rp_id: int) -> None:
        stats = cls.rp_status[rp_id]

        for topic in ServerMqttClient.rp_messages[rp_id].keys():
            sub_topic_mes = ServerMqttClient.rp_messages[rp_id][topic]
            if topic == "cmd":
                ServerMqttClient.rp_cmd[rp_id]["cmd"] = sub_topic_mes
            elif topic == "state":
                stats.state = int(sub_topic_mes)
                cls.client.publish(f"ice_runner/bot_commander/rp_states/{rp_id}/state", stats.state)
            if topic == "dronecan":
                for dronecan_type in sub_topic_mes.keys():
                    dronecan_message = sub_topic_mes[dronecan_type]
                    if dronecan_type == "uavcan.equipment.ice.reciprocating.Status":
                        stats.update_with_resiprocating_status(dronecan_message)
                    if dronecan_type == "uavcan.equipment.ahrs.RawIMU":
                        stats.update_with_raw_imu(dronecan_message)

        topic = f"ice_runner/server/bot_commander/rp_states/{rp_id}/stats"
        cls.client.publish(topic, stats.to_yaml_str()).wait_for_publish()

    def publish_rp_state(cls, rp_id: int) -> None:
        print("publishing rp state")
        cls.client.publish(f"ice_runner/server/bot_commander/rp_states/{rp_id}/state", cls.rp_status[rp_id].state)

    def publish_rp_status(cls, rp_id: int) -> None:
        print("publishing rp status")
        stats = cls.rp_status[rp_id].to_yaml_str()
        cls.client.publish(f"ice_runner/server/bot_commander/rp_states/{rp_id}/stats", stats)


def handle_raspberry_pi_state(client, userdata, msg):
    # print(f"Server:\{msg.topic} received message {msg.topic}: {msg.payload.decode()}")
    rp_id = int(msg.topic.split("/")[2])
    state = int(msg.payload.decode())
    if rp_id not in ServerMqttClient.rp_status.keys():
        ServerMqttClient.rp_status[rp_id] = RPStatus(rp_id, state)
        ServerMqttClient.rp_messages[rp_id] = {}
    ServerMqttClient.rp_status[rp_id].state = state
    client.publish(f"ice_runner/server/bot_commander/rp_states/{rp_id}/state", ServerMqttClient.rp_status[rp_id].state)

def handle_raspberry_pi_dronecan_message(client, userdata, msg):
    rp_id = int(msg.topic.split("/")[2])
    message_type = msg.topic.split("/")[4]
    if rp_id not in ServerMqttClient.rp_messages.keys():
        ServerMqttClient.rp_messages[rp_id] = {}
        print("Add new rp_id to messages")

    if message_type not in ServerMqttClient.rp_messages[rp_id].keys():
        print("Add new message type to messages")
        ServerMqttClient.rp_messages[rp_id][message_type] = {}
    ServerMqttClient.rp_messages[rp_id][message_type] = ast.literal_eval(msg.payload.decode())

# @ServerMqttClient.client.topic_callback("ice_runner/bot/usr_cmd/state")
def handle_bot_usr_cmd_state(client, userdata,  msg):
    print("got bot usr cmd state")
    rp_id = int(msg.payload.decode())
    ServerMqttClient.publish_rp_status(ServerMqttClient, rp_id)
    ServerMqttClient.publish_rp_state(ServerMqttClient, rp_id)

# @ServerMqttClient.client.topic_callback("ice_runner/bot/usr_cmd/stop")
def handle_bot_usr_cmd_stop(client, userdata,  msg):
    print("got bot usr cmd stop")
    rp_id = int(msg.payload.decode())
    ServerMqttClient.client.publish(f"ice_runner/server/bot_commander/{rp_id}/command", "stop")
    ServerMqttClient.client.publish(f"ice_runner/server/bot_commander/{rp_id}/setpoint", 0)
    while True:
        if ServerMqttClient.rp_status[rp_id].state == RPStates.STOPPED.value:
            time.sleep(0.1)
            ServerMqttClient.publish_rp_state(rp_id)
            break
        print(f"Raspberry Pi {rp_id} is stopping. Current state: {ServerMqttClient.rp_status[rp_id].state}")
        time.sleep(0.1)

def start() -> None:
    ServerMqttClient.client.message_callback_add("ice_runner/raspberry_pi/+/state", handle_raspberry_pi_state)
    ServerMqttClient.client.message_callback_add("ice_runner/raspberry_pi/+/dronecan/#", handle_raspberry_pi_dronecan_message)
    ServerMqttClient.client.message_callback_add("ice_runner/bot/usr_cmd/state", handle_bot_usr_cmd_state)
    ServerMqttClient.client.message_callback_add("ice_runner/bot/usr_cmd/stop", handle_bot_usr_cmd_stop)
    ServerMqttClient.client.subscribe("ice_runner/raspberry_pi/#")
    ServerMqttClient.client.subscribe("ice_runner/bot/#")
    ServerMqttClient.client.loop_start()

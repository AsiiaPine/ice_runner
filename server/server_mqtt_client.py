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
from dronecan_communication.DronecanMessages import Message

SETPOINT_STEP = 10

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
        self.start_time: int = None
        self.run_time: int = 0

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
        self.run_time = time.time() - self.start_time

    def update_with_raw_imu(self, status: Dict[str, Any]) -> None:
        self.vibrations = status["integration_interval"]

class IceRunnerConfiguration:
    rpm: int = 4500
    time: int = 0
    max_temperature: int = 190
    max_gas_throttle: int = 0
    report_period: int = 600
    chat_id: int = 0
    max_vibration: int = 100
    min_fuel_volume: int = 0

    @classmethod
    def from_dict(cls, conf: Dict[str, Any]) -> Any:
        cls.rpm = conf["rpm"] if "rpm" in conf.keys() else 4500
        cls.time = conf["time"] if "time" in conf.keys() else 0
        cls.max_temperature = conf["max-temperature"] if "max-temperature" in conf.keys() else 190
        cls.max_gas_throttle = conf["max-gas-throttle"] if "max-gas-throttle" in conf.keys() else 0
        cls.report_period = conf["report-period"] if "report-period" in conf.keys() else 600
        cls.chat_id = conf["chat-id"] if "chat-id" in conf.keys() else 0
        cls.max_vibration = conf["max-vibration"] if "max-vibration" in conf.keys() else 0
        cls.min_fuel_volume = conf["min-fuel-volume"] if "min-fuel-volume" in conf.keys() else 0
        return cls

    def to_dict(self) -> Dict[str, Any]:
        yaml.emitter.Emitter.prepare_tag = lambda self, tag: ''
        return yaml.dump(self, default_flow_style=False)

class ServerMqttClient:
    client = Client(client_id="server", clean_session=True, userdata=None, protocol=MQTTv311, reconnect_on_failure=True)
    rp_messages: Dict[int, Dict[str, Dict[str, Any]]] = {}
    rp_status: Dict[int, RPStatus] = {}
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
        print("started server")

    @classmethod
    def get_client(cls) -> mqtt.client.Client:
        return cls.client

    @classmethod
    def publish_rp_state(cls, rp_id: int) -> None:
        if rp_id not in cls.rp_status.keys():
            print(f"No status for Raspberry Pi {rp_id}")
            return
        print("publishing rp state")
        cls.client.publish(f"ice_runner/server/bot_commander/rp_states/{rp_id}/state", cls.rp_status[rp_id]["state"])

    @classmethod
    def publish_rp_status(cls, rp_id: int) -> None:
        if rp_id not in cls.rp_status.keys():
            return
        stats = cls.rp_status[rp_id]
        print("publishing rp status")
        cls.client.publish(f"ice_runner/server/bot_commander/rp_states/{rp_id}/stats", str(stats))

    @classmethod
    def publish_rp_states(cls) -> None:
        for rp_id, status in cls.rp_status.items():
            cls.publish_rp_state(rp_id)
            cls.publish_rp_status(rp_id)

def handle_raspberry_pi_dronecan_message(client, userdata, msg):
    rp_id = int(msg.topic.split("/")[2])
    print(f"Got dronecan msg for Raspberry Pi {rp_id}: {msg.payload.decode()}")
    message_type: Message = msg.topic.split("/")[4]
    if rp_id not in ServerMqttClient.rp_messages.keys():
        ServerMqttClient.rp_messages[rp_id] = {}
    if message_type not in ServerMqttClient.rp_messages[rp_id].keys():
        ServerMqttClient.rp_messages[rp_id][message_type] = {}
    ServerMqttClient.rp_messages[rp_id][message_type] = yaml.safe_load(msg.payload.decode())

# def handle_raspberry_pi_setpoint(client, userdata, msg):
#     rp_id = int(msg.topic.split("/")[2])
#     # print(f"Got setpoint msg for Raspberry Pi {rp_id}")
#     ServerMqttClient.rp_cur_setpoint[rp_id] = float(msg.payload.decode())

def handle_raspberry_pi_stats(client, userdata, msg):
    rp_id = int(msg.topic.split("/")[2])
    print(f"Got stats msg for Raspberry Pi {rp_id}: {msg.payload.decode()}")
    ServerMqttClient.rp_status[rp_id] = safe_literal_eval(msg.payload.decode())
    ServerMqttClient.client.publish(f"ice_runner/server/bot_commander/rp_states/{rp_id}/state", ServerMqttClient.rp_status[rp_id]["state"])
    ServerMqttClient.client.publish(f"ice_runner/server/bot_commander/rp_states/{rp_id}/stats", str(ServerMqttClient.rp_status[rp_id]))

def handle_raspberry_pi_configuration(client, userdata, msg):
    rp_id = int(msg.topic.split("/")[2])
    print("Hi")
    print(f"Got configuration msg for Raspberry Pi {rp_id}: {msg.payload.decode()}")
    ServerMqttClient.rp_configuration[rp_id] = safe_literal_eval(msg.payload.decode())
    ServerMqttClient.client.publish(f"ice_runner/server/bot_commander/rp_states/{rp_id}/config", str(ServerMqttClient.rp_configuration[rp_id]))
    print(f"Bot got configuration for Raspberry Pi {str(ServerMqttClient.rp_configuration[rp_id])}")


def handle_bot_usr_cmd_state(client, userdata,  msg):
    # print("got bot usr cmd state")
    rp_id = int(msg.payload.decode())
    ServerMqttClient.client.publish("ice_runner/server/rp_commander/get_conf", str(rp_id))
    # time.sleep(0.1)
    # ServerMqttClient.publish_rp_status(rp_id)
    # ServerMqttClient.publish_rp_state(rp_id)

def handle_bot_usr_cmd_stop(client, userdata,  msg):
    print("got bot usr cmd stop")
    rp_id = int(msg.payload.decode())
    ServerMqttClient.client.publish(f"ice_runner/server/bot_commander/{rp_id}/command", "stop")
    ServerMqttClient.rp_setpoint[rp_id] = 0
    ServerMqttClient.client.publish(f"ice_runner/server/bot_commander/{rp_id}/setpoint", 0)
    while True:
        if ServerMqttClient.rp_status[rp_id].state != RPStates.RUNNING.value:
            time.sleep(0.1)
            ServerMqttClient.publish_rp_state(rp_id)
            break
        print(f"Raspberry Pi {rp_id} is stopping. Current state: {ServerMqttClient.rp_status[rp_id].state}")
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
    print("handle_bot_config ", msg.payload.decode())
    rp_id = int(msg.payload.decode())
    print(f"Bot waiting for configuration for Raspberry Pi {rp_id}")
    if rp_id not in ServerMqttClient.rp_configuration.keys():
        ServerMqttClient.rp_configuration[rp_id] = {}
    ServerMqttClient.client.publish(f"ice_runner/server/rp_commander/config", str(rp_id))
    print(f"waiting for configuration for Raspberry Pi {rp_id}")

def start() -> None:
    ServerMqttClient.client.message_callback_add("ice_runner/raspberry_pi/+/stats", handle_raspberry_pi_stats)
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

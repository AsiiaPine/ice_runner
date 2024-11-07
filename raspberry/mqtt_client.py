import ast
import os
import sys
import time
from typing import Any, Dict, List
from paho import mqtt
from paho.mqtt.client import MQTTv311
import yaml
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from dronecan_communication.DronecanMessages import Message
from common.RPStates import RPStates
'''*rpm*:
    default: 4500
    description: Целевые обороты ДВС\n
*max-temperature*:
    default: 190
    description: Максимальная допустимая температура ДВС, после которой скрипт завершит выполнение\n
*max-gas-throttle*:
    dafeult: 100
    description: Максимальное допустимый уровень газовой заслонки в процентах. Значение 100 означает, что нет ограничений.\n
*report-period*:
    default: 600
    description: Период публикации статус сообщения в секундах \n
*chat-id*:
    default: None
    description: Идентификатор телеграм-чата, с которым бот будет взаимодействовать.\n
*time*:
    default: None
    description: Время в секундах, через которое скрипт автоматически закончит свое выполнение
*max-vibration*:
    default: None
    description: Максимальный допустимый уровень вибрации\n
*min-fuel-volume*:
    default: 0
    description: Минимальный уровень топлива (% или cm3), после которого прекращаем обкатку/выдаем предупреждение.
'''

class ICERunnerConfiguration:
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

class RaspberryMqttClient:
    client = mqtt.client.Client(client_id="raspberry_0", clean_session=True, userdata=None, protocol=MQTTv311)
    rp_id: int = 0
    last_message_receive_time = 0
    setpoint_command: float = 0
    state = RPStates.WAITING
    configuration: ICERunnerConfiguration = ICERunnerConfiguration

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
    def publish_state(cls, state: Dict[str, Dict[str, Message]]) -> None:
        for node_type in state.keys():
            for dronecan_type in state[node_type].keys():
                cls.client.publish(f"ice_runner/raspberry_pi/{cls.rp_id}/dronecan/{dronecan_type}", str(state[node_type][dronecan_type].to_dict()))
        cls.client.publish(f"ice_runner/raspberry_pi/{cls.rp_id}/state", cls.state.value)
        cls.client.publish(f"ice_runner/raspberry_pi/{cls.rp_id}/setpoint", cls.setpoint_command)

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
        RaspberryMqttClient.last_message_receive_time = time.time()

def handle_setpoint(client, userdata, message):
    print(f"RP:\t{message.topic}: {message.payload.decode()}")
    RaspberryMqttClient.setpoint_command = int(message.payload.decode())

def handle_config(client, userdata, message):
    print("RP:\tConfiguration")
    # RaspberryMqttClient.configuration = ast.literal_eval(message.payload.decode())
    RaspberryMqttClient.configuration = ICERunnerConfiguration.from_dict(ast.literal_eval(message.payload.decode()))
    # print(RaspberryMqttClient.configuration)


def start() -> None:
    RaspberryMqttClient.client.message_callback_add(f"ice_runner/server/raspberry_pi_commander/{RaspberryMqttClient.rp_id}/command", handle_command)

    RaspberryMqttClient.client.message_callback_add(f"ice_runner/server/raspberry_pi_commander/{RaspberryMqttClient.rp_id}/config", handle_config)

    RaspberryMqttClient.client.message_callback_add(f"ice_runner/server/raspberry_pi_commander/{RaspberryMqttClient.rp_id}/setpoint", handle_setpoint)

    RaspberryMqttClient.client.subscribe(f"ice_runner/server/raspberry_pi_commander/{RaspberryMqttClient.rp_id}/#")
    RaspberryMqttClient.client.loop_start()

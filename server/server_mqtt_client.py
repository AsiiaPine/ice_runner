from enum import IntEnum
from MQTTClientBase import MqttClient
from paho import mqtt
from paho.mqtt.client import MQTTv311, Client
import ast

class RPStates(IntEnum):
    READY = 0
    STARTING = 1
    RUNNING = 2
    STOPPING = 3
    STOPPED = 4

class ServerMqttClient(MqttClient):
    client = Client(client_id="server", clean_session=True, userdata=None, protocol=MQTTv311, reconnect_on_failure=True)
    rp_states = {}
    def __init__(self, client_id: str = "server", server_ip: str = "localhost", port: int = 1883, max_messages: int = 10) -> None:
        super().__init__(client_id, server_ip, port, max_messages)
        # global client
        self.subscribe(f"ice_runner/raspberry_pi/#")

        self.subscribe("bot")
        self.publish("commander", f"ready {client_id}")
        self.connected_clients = []
        print(f"ServerMqttClient {client_id} connected")

    def on_message(self, client, userdata, msg):
        # print(f"SERVER:\t{msg.topic} received message {msg.topic}: {msg.payload.decode()}")
        super().on_message(client, userdata, msg)
        if "bot" in msg.topic:
            print(f"Server:\tBot {msg.topic} received message {msg.topic}: {msg.payload.decode()}")
            if msg.payload.decode() == "start":
                print("Server:\tBot start")
                for raspberry_id in range(1, 4):
                    self.publish(f"raspberry_{raspberry_id}_commander", "start")
            if msg.payload.decode() == "stop":
                print("Server:\tBot stop")
                for raspberry_id in range(1, 4):
                    self.publish(f"raspberry_{raspberry_id}_commander", "stop")
            if msg.payload.decode() == "stop_all":
                print("Server:\tBot stop all")
                for raspberry_id in range(1, 4):
                    self.publish(f"raspberry_{raspberry_id}_commander", "stop_all")
            if msg.payload.decode() == "configuration":
                print("Server:\tBot configuration")
                for raspberry_id in range(1, 4):
                    self.publish("raspberry_{raspberry_id}_commander", "configuration")
            if msg.payload.decode() == "stop_all":
                print("Server:\tBot stop all")
                for raspberry_id in range(1, 4):
                    self.publish(f"raspberry_{raspberry_id}_commander", "stop_all")

    def publish_stop(self, ice_id: int) -> None:
        self.publish("commander", f"stop {ice_id}")

    def publish(self, topic, message):
        print(f"Server:\tServerrMqttClient publish {topic}: {message}")
        return super().publish(topic, message)


# TODO: specify callbacks for each topic with
@ServerMqttClient.client.topic_callback("ice_runner/raspberry_pi/#/state")
def handle_raspberry_pi(client, userdata, msg):
    print(f"Server:\tRaspberry Pi {msg.topic} received message {msg.topic}: {msg.payload.decode()}")
    rp_id = int(msg.topic.split("/")[2])
    state = RPStates(int(msg.payload.decode()))
    ServerMqttClient.rp_states[rp_id] = state

@ServerMqttClient.client.topic_callback("ice_runner/raspberry_pi/#/ice/esc.Status")
def handle_raspberry_pi_esc_status(client, userdata, msg):
    rp_id = int(msg.topic.split("/")[2])
    message = ast.literal_eval(msg.payload.decode())

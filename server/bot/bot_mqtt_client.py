from typing import Dict, List
import paho.mqtt.client as paho
from paho import mqtt
from paho.mqtt.client import MQTTv311

class MqttClient:
    def __init__(self, client_id: str, server_ip: str, port: int, max_messages: int = 10) -> None:
        self.client = paho.Client(client_id=client_id, clean_session=True, userdata=None, protocol=MQTTv311)
        self.client.on_message = self.on_message
        self.client.connect(server_ip, port, 60)
        self.received_messages: Dict[str, List[str]] = {}
        self.max_messages = max_messages

    def subscribe(self, topic: str) -> None:
        self.client.subscribe(topic)

    def on_message(self, client, userdata, msg):
        print(msg.topic + ": " + msg.payload.decode())
        self.received_messages[msg.topic].append(msg.payload.decode())
        if len(self.received_messages[msg.topic]) > self.max_messages:
            self.received_messages[msg.topic].pop(0)

    def publish(self, topic: str, message: str) -> None:
        self.client.publish(topic, message)

    def loop_forever(self) -> None:
        try:
            print("Press CTRL+C to exit")
            self.client.loop_forever()
        except:
            print("Exiting...")

    def disconnect(self) -> None:
        self.client.disconnect()

    def reconnect(self) -> None:
        self.client.reconnect()

class BotMqttClient(MqttClient):
    def __init__(self, client_id: str = "bot", server_ip: str = "localhost", port: int = 1883, max_messages: int = 10) -> None:
        super().__init__(client_id, server_ip, port, max_messages)
        self.critical_clients = ["raspberry"]

    def subscribe(self, topic: str) -> None:
        super().subscribe(topic)
        self.received_messages[topic] = []

    def on_message(self, client, userdata, msg):
        if client.client_id in self.critical_clients:
            print(f"Critical client {client.client_id} received message {msg.topic}: {msg.payload.decode()}")
            if msg.payload.decode() == "stopped":
                print("Stopping")

class ServerMqttClient(MqttClient):
    def __init__(self, client_id: str = "server", server_ip: str = "localhost", port: int = 1883, max_messages: int = 10) -> None:
        super().__init__(client_id, server_ip, port, max_messages)
        self.critical_clients = ["bot", "raspberry"]
        # self.subscribe("uavcan.protocol.NodeStatus")
        self.subscribe("nodes_status")

    def on_message(self, client, userdata, msg):
        if client.client_id in self.critical_clients:
            print(f"Critical client {client.client_id} received message {msg.topic}: {msg.payload.decode()}")
            if msg.payload.decode() == "stopped":
                print("Stopping")

    def publish_stop(self, ice_id: int) -> None:
        self.publish("commander", f"stop {ice_id}")

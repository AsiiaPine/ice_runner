import time
from typing import Dict, List
import paho.mqtt.client as paho
from paho import mqtt
from paho.mqtt.client import MQTTv311

class RaspberryMqttClient:
    def __init__(self, client_id: str, server_ip: str, port: int, max_messages: int = 2) -> None:
        self.client = mqtt.client.Client(client_id=client_id, clean_session=True, userdata=None, protocol=MQTTv311)
        self.client.on_message = self.on_message
        self.client.connect(server_ip, port, 60)
        self.received_messages: Dict[str, List[str]] = {}
        self.max_messages = max_messages
        # self.critical_topics = ["commander"]
        self.clients_to_listen = ["commander"]
        self.last_message_receive_time = 0
        self.client.subscribe("commander")

    def subscribe(self, topic: str) -> None:
        self.client.subscribe(topic)
        self.received_messages[topic] = []

    def on_message(self, client, userdata, msg):
        if client.client_id not in self.clients_to_listen:
            print(msg.topic + ": " + msg.payload.decode())
            return
        if len(self.received_messages[msg.topic]) > self.max_messages:
            self.received_messages[msg.topic].pop(0)
        self.received_messages[msg.topic].append(msg.payload.decode())
        self.last_message_receive_time = time.time()

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

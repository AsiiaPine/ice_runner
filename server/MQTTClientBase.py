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
        self.client.loop_start()

    def subscribe(self, topic: str) -> None:
        if topic not in self.received_messages.keys():
            self.received_messages[topic] = [None]
        self.client.subscribe(topic)

    def on_message(self, client, userdata, msg):
        print(client._client_id.decode("utf-8"), userdata, msg.topic + ": " + msg.payload.decode())
        self.received_messages[msg.topic].append(msg.payload.decode())
        if len(self.received_messages[msg.topic]) > self.max_messages:
            self.received_messages[msg.topic].pop(0)

    def publish(self, topic: str, message: str) -> None:
        print(f"{self.client._client_id} publish {topic}: {message}")
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

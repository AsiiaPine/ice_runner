import time
from typing import Dict, List
import paho.mqtt.client as paho
from paho import mqtt
from paho.mqtt.client import MQTTv311

# TODO: specify callbacks for each topic with
# @client.topic_callback("mytopic/#")
# def handle_mytopic(client, userdata, message):


class RaspberryMqttClient:
    def __init__(self, rp_id: str, server_ip: str, port: int = 1883, max_messages: int = 2) -> None:
        self.client = mqtt.client.Client(client_id=f"raspberry_{rp_id}", clean_session=True, protocol=MQTTv311)
        self.client.on_message = self.on_message
        self.client.connect(server_ip, port, 60)
        self.received_messages: Dict[str, List[str]] = {"commander": [None], f"raspberry_{rp_id}_commander": [None]}
        print(len(self.received_messages[f"raspberry_{rp_id}_commander"]))
        self.max_messages = max_messages
        self.last_message_receive_time = 0
        self.publish(f"raspberry_pi", f"raspberry_{rp_id} ready")
        self.client.subscribe("commander")
        self.client.subscribe(f"raspberry_{rp_id}_commander")
        self.client.loop_start()

    def subscribe(self, topic: str) -> None:
        self.client.subscribe(topic)
        self.received_messages[topic] = []

    def on_message(self, client, userdata, msg):
        print("RP:\t" + msg.topic + ": " + msg.payload.decode())
        # if client._client_id.decode() not in self.clients_to_listen:
            # print(f"RP:\t we don't listen to this client, {client._client_id}, clients we listen to: {self.clients_to_listen}")
            # return
        if len(self.received_messages[msg.topic]) > self.max_messages:
            self.received_messages[msg.topic].pop(0)
        self.received_messages[msg.topic].append(msg.payload.decode())
        self.last_message_receive_time = time.time()
        if msg.topic == "commander":
            if msg.payload.decode() == "ready":
                print("RP:\tServer is ready")
                self.publish(client._client_id, "ready")
            if msg.payload.decode() == client._client_id:
                print("RP:\tServer registered")

    def publish(self, topic: str, message: str) -> None:
        print(f"RP:\tPublish {topic}: {message}")
        self.client.publish(topic, message)

    def loop_forever(self) -> None:
        try:
            print("RP:\tPress CTRL+C to exit")
            self.client.loop_forever()
        except:
            print("RP:\tExiting...")

    def disconnect(self) -> None:
        self.client.disconnect()

    def reconnect(self) -> None:
        self.client.reconnect()

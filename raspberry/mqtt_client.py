import time
from typing import Dict, List
import paho.mqtt.client as paho
from paho import mqtt
from paho.mqtt.client import MQTTv311

# TODO: specify callbacks for each topic with
# @client.topic_callback("mytopic/#")
# def handle_mytopic(client, userdata, message):


class RaspberryMqttClient:
    client = mqtt.client.Client(client_id="raspberry_0", clean_session=True, userdata=None, protocol=MQTTv311)
    rp_id: int = 0

    @classmethod
    def get_client(cls) -> mqtt.client.Client:
        return cls.client

    @classmethod
    def connect(cls, rp_id: int, server_ip: str, port: int = 1883, max_messages: int = 2) -> None:
        cls.rp_id = rp_id
        cls.client = mqtt.client.Client(client_id=f"raspberry_{rp_id}", clean_session=True, protocol=MQTTv311)
        cls.client.connect(server_ip, port, 60)
        cls.client.subscribe(f"ice_runner/server/rp_commander/{rp_id}/#")
        cls.client.loop_start()
        cls.client.publish(f"ice_runner/raspberry_pi/{rp_id}/state", "ready")

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

@RaspberryMqttClient.client.topic_callback("ice_runner/server/rp_commander/{rp_id}/command")
def handle_command(client, userdata, message):
    print(f"RP:\t{message.topic}: {message.payload.decode()}")
    if message.payload.decode() == "start":
        print("RP:\tStart")
        is_started = True
    if message.payload.decode() == "stop" or message.payload.decode() == "stop_all":
        print("RP:\tStop")
        is_started = False
    if message.payload.decode() == "run":
        if is_started:
            print("RP:\tRun")
        else: 
            print("RP:\tCall Start first")
            client.client

    

@classmethod
@RaspberryMqttClient.client.topic_callback("ice_runner/raspberry_pi/{rp_id}/conf")
def handle_conf(client, userdata, message):
    print("RP:\tConfiguration")

RaspberryMqttClient.client.message_callback_add("ice_runner/server/rp_commander/{rp_id}/command", handle_command)
RaspberryMqttClient.client.message_callback_add("ice_runner/raspberry_pi/{rp_id}/conf", handle_conf)

    # def __init__(self, rp_id: str, server_ip: str, port: int = 1883, max_messages: int = 2) -> None:
    #     self.client = mqtt.client.Client(client_id=f"raspberry_{rp_id}", clean_session=True, protocol=MQTTv311)
    #     self.client.on_message = self.on_message
    #     self.client.connect(server_ip, port, 60)
    #     self.max_messages = max_messages
    #     self.last_message_receive_time = 0
    #     self.publish(f"ice_runner/raspberry_pi/{rp_id}/state", "ready")
    #     self.client.subscribe(f"ice_runner/server/rp_commander/{rp_id}/#")
    #     self.client.loop_start()


    # def on_message(self, client, userdata, msg):
    #     print("RP:\t" + msg.topic + ": " + msg.payload.decode())
    #     # if client._client_id.decode() not in self.clients_to_listen:
    #         # print(f"RP:\t we don't listen to this client, {client._client_id}, clients we listen to: {self.clients_to_listen}")
    #         # return
    #     if len(self.received_messages[msg.topic]) > self.max_messages:
    #         self.received_messages[msg.topic].pop(0)
    #     self.received_messages[msg.topic].append(msg.payload.decode())
    #     self.last_message_receive_time = time.time()
    #     if msg.topic == "commander":
    #         if msg.payload.decode() == "ready":
    #             print("RP:\tServer is ready")
    #             self.publish(client._client_id, "ready")
    #         if msg.payload.decode() == client._client_id:
    #             print("RP:\tServer registered")

    # def publish(self, topic: str, message: str) -> None:
    #     print(f"RP:\tPublish {topic}: {message}")
    #     self.client.publish(topic, message)

    # def loop_forever(self) -> None:
    #     try:
    #         print("RP:\tPress CTRL+C to exit")
    #         self.client.loop_forever()
    #     except:
    #         print("RP:\tExiting...")

    # def disconnect(self) -> None:
    #     self.client.disconnect()

    # def reconnect(self) -> None:
    #     self.client.reconnect()

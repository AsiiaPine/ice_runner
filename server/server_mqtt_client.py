from MQTTClientBase import MqttClient
from paho import mqtt
from paho.mqtt.client import MQTTv311, Client

class ServerMqttClient(MqttClient):
    client = Client(client_id="server", clean_session=True, userdata=None, protocol=MQTTv311)
    def __init__(self, client_id: str = "server", server_ip: str = "localhost", port: int = 1883, max_messages: int = 10) -> None:
        super().__init__(client_id, server_ip, port, max_messages)
        # global client
        # self.subscribe("uavcan.protocol.NodeStatus")
        # self.subscribe("nodes_status")
        self.subscribe("raspberry_pi")
        for raspberry_id in range(1, 6):
            self.subscribe(f"raspberry_{raspberry_id}")


        self.subscribe("bot")
        self.publish("commander", f"ready {client_id}")
        self.connected_clients = []
        print(f"ServerMqttClient {client_id} connected")

    def on_message(self, client, userdata, msg):
        # print(f"SERVER:\t{msg.topic} received message {msg.topic}: {msg.payload.decode()}")
        super().on_message(client, userdata, msg)
        # if "raspberry" in msg.topic:
        #     print(f"SERVER:\tRaspberry Pi {client._client_id} received message {msg.topic}: {msg.payload.decode()}")
        #     if msg.payload.decode() == "ready":
        #         print("SERVER:\tRaspberry Pi ready")
        #         self.publish("commander", f"{msg.topic} ready")
        #         self.publish("commander", f"{msg.topic} ready")
        # if "raspberry_pi" == msg.topic:
        #     print(f"SERVER:\tRaspberry Pi {msg.topic} received message {msg.topic}: {msg.payload.decode()}")
        #     rp_topic, message = msg.payload.decode().split(" ", maxsplit=1)
        #     if message == "ready":
        #         print(f"SERVER:\t{rp_topic} ready")
        #         self.subscribe(rp_topic)
        #         self.publish(f"{rp_topic}_commander", f"registered")
        if "bot" in msg.topic:
            print(f"Serve:\tBot {msg.topic} received message {msg.topic}: {msg.payload.decode()}")
            if msg.payload.decode() == "start":
                print("Serve:\tBot start")
                for raspberry_id in range(1, 4):
                    self.publish(f"raspberry_{raspberry_id}_commander", "start")
            if msg.payload.decode() == "stop":
                print("Serve:\tBot stop")
                for raspberry_id in range(1, 4):
                    self.publish(f"raspberry_{raspberry_id}_commander", "stop")
            if msg.payload.decode() == "stop_all":
                print("Serve:\tBot stop all")
                for raspberry_id in range(1, 4):
                    self.publish(f"raspberry_{raspberry_id}_commander", "stop_all")
            if msg.payload.decode() == "configuration":
                print("Serve:\tBot configuration")
                for raspberry_id in range(1, 4):
                    self.publish("raspberry_{raspberry_id}_commander", "configuration")
            if msg.payload.decode() == "stop_all":
                print("Serve:\tBot stop all")
                for raspberry_id in range(1, 4):
                    self.publish(f"raspberry_{raspberry_id}_commander", "stop_all")

    def publish_stop(self, ice_id: int) -> None:
        self.publish("commander", f"stop {ice_id}")

    def publish(self, topic, message):
        print(f"Serve:\tServerMqttClient publish {topic}: {message}")
        return super().publish(topic, message)


# TODO: specify callbacks for each topic with
@ServerMqttClient.client.topic_callback("raspberry_pi/#")
def handle_raspberry_pi(client, userdata, msg):
    print(f"Server received message user:{userdata} {message.topic}: {message.payload.decode()}")
    print(f"SERVER:\tRaspberry Pi {msg.topic} received message {msg.topic}: {msg.payload.decode()}")
    rp_topic, message = msg.payload.decode().split(" ", maxsplit=1)
    if message == "ready":
        print(f"SERVER:\t{rp_topic} ready")
        client.subscribe(rp_topic)
        client.publish(f"{rp_topic}_commander", f"registered")

def handle_raspberry_msg(id, client, userdata, msg):
    print(f"Server received message user:{userdata} {msg.topic}: {msg.payload.decode()}")
    print(f"SERVER:\tRaspberry 1 {msg.topic} received message {msg.topic}: {msg.payload.decode()}")
    client.publish(f"raspberry_{id}_commander", f"received {msg.topic}")

@ServerMqttClient.client.topic_callback("raspberry_1/#")
def handle_raspberry_1(client, userdata, msg):
    ServerMqttClient.handle_raspberry_msg(1, client, userdata, msg)
@ServerMqttClient.client.topic_callback("raspberry_2/#")
def handle_raspberry_2(client, userdata, msg):
    ServerMqttClient.handle_raspberry_msg(2, client, userdata, msg)
@ServerMqttClient.client.topic_callback("raspberry_3/#")
def handle_raspberry_3(client, userdata, msg):
    ServerMqttClient.handle_raspberry_msg(3, client, userdata, msg)
@ServerMqttClient.client.topic_callback("raspberry_4/#")
def handle_raspberry_4(client, userdata, msg):
    ServerMqttClient.handle_raspberry_msg(4, client, userdata, msg)
@ServerMqttClient.client.topic_callback("raspberry_5/#")
def handle_raspberry_5(client, userdata, msg):
    ServerMqttClient.handle_raspberry_msg(5, client, userdata, msg)

ServerMqttClient.client.message_callback_add("raspberry_pi/#", handle_raspberry_pi)
ServerMqttClient.client.message_callback_add(f"raspberry_{1}/#", handle_raspberry_1)
ServerMqttClient.client.message_callback_add(f"raspberry_{2}/#", handle_raspberry_2)
ServerMqttClient.client.message_callback_add(f"raspberry_{3}/#", handle_raspberry_3)
ServerMqttClient.client.message_callback_add(f"raspberry_{4}/#", handle_raspberry_4)
ServerMqttClient.client.message_callback_add(f"raspberry_{5}/#", handle_raspberry_5)

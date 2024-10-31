from MQTTClientBase import MqttClient

client = MqttClient("bot", "localhost", 1883)

class BotMqttClient(MqttClient):
    def __init__(self, client_id: str = "bot", server_ip: str = "localhost", port: int = 1883, max_messages: int = 10) -> None:
        super().__init__(client_id, server_ip, port, max_messages)
        self.client = client
        # self.critical_clients = [f"raspberry_pi_{id}" for id in range(1, 4)]
        self.critical_clients = []
        self.client.client.message_callback_add(f"commander/#", self.handle_commander)

    def subscribe(self, topic: str) -> None:
        super().subscribe(topic)
        self.received_messages[topic] = []

    def on_message(self, client, userdata, msg):
        super().on_message(client, userdata, msg)
        if client._client_id in self.critical_clients:
            print(f"Critical client {client._client_id} received message {msg.topic}: {msg.payload.decode()}")
            if msg.payload.decode() == "stopped":
                print("Stopping")

    # TODO: specify callbacks for each topic with
    # @client.topic_callback("commander/#")
    def handle_commander(client, userdata, message):
        print(f"Bot received message user:{userdata} {message.topic}: {message.payload.decode()}")


# class ServerMqttClient(MqttClient):
#     def __init__(self, client_id: str = "server", server_ip: str = "localhost", port: int = 1883, max_messages: int = 10) -> None:
#         super().__init__(client_id, server_ip, port, max_messages)
#         # self.subscribe("uavcan.protocol.NodeStatus")
#         # self.subscribe("nodes_status")
#         self.subscribe("raspberry_pi")
#         self.subscribe("bot")
#         self.publish("commander", "ready")
#         self.connected_clients = []
#         print(f"ServerMqttClient {client_id} connected")

#     def on_message(self, client, userdata, msg):
#         print(f"SERVER:\t{client._client_id} received message {msg.topic}: {msg.payload.decode()}")
#         super().on_message(client, userdata, msg)
#         if client._client_id not in self.connected_clients:
#             self.connected_clients.append(client._client_id)

#         if "raspberry" in client._client_id.decode("utf-8"):
#             print(f"SERVER:\tRaspberry Pi {client._client_id} received message {msg.topic}: {msg.payload.decode()}")
#             if msg.payload.decode() == "ready":
#                 print("SERVER:\tRaspberry Pi ready")
#                 self.publish("bot", f"{client._client_id} ready")
#         if "bot" in client._client_id.decode("utf-8"):
#             print(f"Serve:\tBot {client._client_id} received message {msg.topic}: {msg.payload.decode()}")
#             if msg.payload.decode() == "start":
#                 print("Serve:\tBot start")
#                 for raspberry_id in range(1, 4):
#                     self.publish(f"raspberry_{raspberry_id}_commander", "start")
#             if msg.payload.decode() == "stop":
#                 print("Serve:\tBot stop")
#                 for raspberry_id in range(1, 4):
#                     self.publish(f"raspberry_{raspberry_id}_commander", "stop")
#             if msg.payload.decode() == "stop_all":
#                 print("Serve:\tBot stop all")
#                 for raspberry_id in range(1, 4):
#                     self.publish(f"raspberry_{raspberry_id}_commander", "stop_all")
#             if msg.payload.decode() == "configuration":
#                 print("Serve:\tBot configuration")
#                 self.publish("raspberry_pi", "configuration")
#             if msg.payload.decode() == "stop_all":
#                 print("Serve:\tBot stop all")
#                 for raspberry_id in range(1, 4):
#                     self.publish(f"raspberry_{raspberry_id}_commander", "stop_all")

#     def publish_stop(self, ice_id: int) -> None:
#         self.publish("commander", f"stop {ice_id}")

#     def publish(self, topic, message):
#         print(f"Serve:\tServerMqttClient publish {topic}: {message}")
#         return super().publish(topic, message)

    

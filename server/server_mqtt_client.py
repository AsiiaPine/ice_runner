from MQTTClientBase import MqttClient

client: MqttClient = None

class ServerMqttClient(MqttClient):
    def __init__(self, client_id: str = "server", server_ip: str = "localhost", port: int = 1883, max_messages: int = 10) -> None:
        super().__init__(client_id, server_ip, port, max_messages)
        global client
        client = self.client
        # self.subscribe("uavcan.protocol.NodeStatus")
        # self.subscribe("nodes_status")
        self.subscribe("raspberry_pi")
        for raspberry_id in range(1, 4):
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
        if "raspberry_pi" == msg.topic:
            print(f"SERVER:\tRaspberry Pi {msg.topic} received message {msg.topic}: {msg.payload.decode()}")
            rp_topic, message = msg.payload.decode().split(" ", maxsplit=1)
            if message == "ready":
                print(f"SERVER:\t{rp_topic} ready")
                self.subscribe(rp_topic)
                self.publish(f"{rp_topic}_commander", f"registered")
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
    @client.topic_callback("commander/#")
    def handle_commander(client, userdata, message):
        print(f"Server received message user:{userdata} {message.topic}: {message.payload.decode()}")

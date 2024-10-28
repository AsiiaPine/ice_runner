import os
import sys
from dotenv import load_dotenv

import paho.mqtt.client as paho
from paho import mqtt
from paho.mqtt.client import MQTTv311
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '../raspberry_pi')))
from DronecanMessages import NodeStatus

load_dotenv()

SERVER_IP = os.getenv("SERVER_IP")

client = mqtt.client.Client(client_id="", clean_session=True, userdata=None, protocol=MQTTv311)
node_status = NodeStatus(uptime_sec=100, health=NodeStatus.Health(NodeStatus.Health.HEALTH_OK), mode=NodeStatus.Mode(NodeStatus.Mode.MODE_OPERATIONAL), sub_mode=0, vendor_specific_status_code=0)

if client.connect(SERVER_IP, 1883, 60) != 0:
    print("Couldn't connect to MQTT broker!")
    sys.exit(-1)
string = ''
for name, value in node_status.to_dict().items():
    string += f"{name}: {value}\n"
client.publish("uavcan.protocol.NodeStatus", string)
client.publish("test/status", "Hello World!")
print("Published message!")

try:
    print("Press CTRL+C to exit")
    client.loop_forever()
except:
    print("Exiting...")

client.disconnect()

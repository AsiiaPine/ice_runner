import sys
# import paho.mqtt.client as paho
from paho.mqtt import client as mqtt_client
from paho.mqtt.client import MQTTv311

def on_message(client, userdata, msg):
    print(msg.topic + ": " + msg.payload.decode())

# client = paho.Client()
client = mqtt_client.Client(client_id="", clean_session=True, userdata=None, protocol=MQTTv311)
client.on_message = on_message

# if client.connect("localhost", 1883, 60) != 0:
if client.connect("10.100.8.235", 1883, 60) != 0:
    print("Couldn't connect to MQTT broker!")
    sys.exit(-1)

client.subscribe("test/status")
client.subscribe("uavcan.protocol.NodeStatus")
try:
    print("Press CTRL+C to exit")
    client.loop_forever()
except:
    print("Exiting...")

client.disconnect()

import sys
import paho.mqtt.client as paho
from paho import mqtt
from paho.mqtt.client import MQTTv311
# def on_message(client, userdata, msg):
#     print(msg.topic + ": " + msg.payload.decode())


client = mqtt.client.Client(client_id="", clean_session=True, userdata=None, protocol=MQTTv311)
# client.on_message = on_message

if client.connect("localhost", 1883, 60) != 0:
# if client.connect("10.100.8.235", 1883, 60) != 0:
    print("Couldn't connect to MQTT broker!")
    sys.exit(-1)

client.publish("test/status", "Hello World!")
print("Published message!")
try:
    print("Press CTRL+C to exit")
    client.loop_forever()
except:
    print("Exiting...")

client.disconnect()

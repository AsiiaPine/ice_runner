from enum import IntEnum
import time
from typing import Any, Dict, List
import paho.mqtt.client as paho
from paho import mqtt
from paho.mqtt.client import MQTTv311

n_mes = 0
mes_rate = 0
prev_time = time.time()
def on_message(client, userdata, msg):
    global n_mes
    global mes_rate
    global prev_time
    n_mes += 1
    if time.time() - prev_time > 1:
        mes_rate = n_mes
        n_mes = 0
        prev_time = time.time()
    print(mes_rate, msg.topic + ": " + msg.payload.decode())

client = mqtt.client.Client(client_id="raspberry_0", clean_session=True, userdata=None, protocol=MQTTv311)
client.connect("localhost", 1883, 60)
client.subscribe("ice_runner/raspberry_pi/#")
client.on_message = on_message
client.loop_forever()


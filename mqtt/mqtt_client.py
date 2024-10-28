import paho.mqtt.client as mqtt
import ssl

version = '5' # or '3' 
mytransport = 'websockets' # or 'tcp'

if version == '5':
    client = mqtt.Client(client_id="myPy",
                         transport=mytransport,
                         protocol=mqtt.MQTTv5)
if version == '3':
    client = mqtt.Client(client_id="myPy",
                         transport=mytransport,
                         protocol=mqtt.MQTTv311,
                         clean_session=True)

# ice_runner

The project is a contoller for Internal Combustion engines (ICE) runners. Each ICE is connected to RaccoonLab Dronecan ice_node. The ice_nodes are connected to individual Raspberry Pi. 

One can control the ICE runners using the telegram bot. The bot can send commands to the Raspberry Pi and receive the statuses and logs from the Raspberry Pi.

## Requirements

- Raspberry Pi
- ICE block

## How to run the project 
0. Setup the environment
    - Specify telergam bot token, chat_id and mqtt server ip in the file `.env`.
    e.g.
    ```
    BOT_TOKEN=***
    SERVER_PORT = 1883
    SERVER_IP=localhost
    CHAT_ID=***
    ```
    - Setup the virtual environment
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    pip install -e . # Install the project common part
    ```

1. Raspberry Pi ICE controller installation
    - Install mqtt broker
        ```bash
        sudo apt-get update
        sudo apt-get install mosquitto mosquitto-clients
        ```
    - Change ice runner configuration in `ice_configuration.yml` (you can change the configuration using telegram bot's command `/config`)
    - Run the script with the specified id for the raspberry pi. This id is used for MQTT communication and in telegram bot commands.
        ```bash
        ./raspberry/main.py --id 1
        ```

2. Server installation
Use the [guide](https://www.atlantic.net/dedicated-server-hosting/how-to-install-mosquitto-mqtt-server-on-ubuntu-22-04/) to start your own Mosquitto MQTT server on your machine

    - Install required packages
        ```bash
        ./prepare_mqtt_server.sh
        ```
        To allow anonymous access to the server and setup the used port, edit the file `/etc/mosquitto/mosquitto.conf`:
        ```
        allow_anonymous true
        listener 1883 0.0.0.0
        ```
    - Run the script
        ```bash
        ./server/main.py
        ```
3. Bot start
    - Run the script

        ```bash
        ./bot/main.py
        ```

To start a simulator of the ICE start can interface (e.g. slcan/vcan), run the following script:

```bash
./ice_sim/test_commander.py
```

## Project structure
Server is the main controller of the project.
Server and Bot are asynchronous processes and communicate with each other using MQTT protocol. Therefore all parts of the project are independent and connected by MQTT.
    ![Project structure](assets/auto_ice.png)
### MQTT communication diagram
Server subscribes to bot and rp topics and sends commands and statuses to the respective topics with commander suffix.
Bot subscribes to its commander topic and sends user commands to the server.
Raspberry Pi subscribes to its commander topic and sends parsed dronecan messages to the server.
    ![MQTT communication diagram](assets/mqtt_diagram.svg)


# TODO:
- [ ] Fix the command sending rate of ice_commander

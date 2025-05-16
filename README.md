# ice_runner

The project is a contoller for Internal Combustion engines (ICE) runners. Each ICE is connected to RaccoonLab Dronecan ice_node. The ice_nodes are connected to individual Raspberry Pi. 

One can control the ICE runners using the telegram bot. The bot can send commands to the Raspberry Pi and receive its status and logs.

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
    CHAT_ID=*** # the bot will be awailable in this chat only
    RUNNER_ID=1 # the id of the raspberry pi (if you have more than one raspberry pi, you can specify the id of the raspberry pi you want to control)
    ```
    - Setup the virtual environment
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```
### Simple run with system check once per minute (default)
```bash
./scripts/start_all.sh venv 60
```

### Running all jobs separately
1. Raspberry Pi ICE controller
    - Install mqtt broker
        ```bash
        sudo ./scripts/install_mqtt.sh
        ```
    - Change ice runner configuration in `ice_configuration.yml` (you can change the configuration using telegram bot's command `/config`)
    - Run the script with the specified id for the raspberry pi. This id is used for MQTT communication and in telegram bot commands.
        ```bash
         ./src/ice_runner/main.py client --id 1 --config ice_configuration.yml
        ```

2. Server
Use the [guide](https://www.atlantic.net/dedicated-server-hosting/how-to-install-mosquitto-mqtt-server-on-ubuntu-22-04/) to start your own Mosquitto MQTT server on your machine

    - Install required packages
        ```bash
        ./scripts/install_mqtt.sh
        ```
        To allow anonymous remote access to the server and setup the used port, edit the file `/etc/mosquitto/mosquitto.conf`:
        ```
        allow_anonymous true
        listener 1883 0.0.0.0
        ```
    - Run the script
        ```bash
        ./src/ice_runner/main.py srv
        ```
3. Bot start
    - Run the script

        ```bash
         ./src/ice_runner/main.py bot
        ```
### Simulator
To start a simulator of the ICE start can interface (e.g. slcan/vcan), run the following script:

```bash
./src/ice_runner/main.py sim --n_tries=3 --log_dir=logs --vcan=can0
```
One can specify the number of tries to start the engine with the `--n_tries` parameter. The default value is 3.
Also, one can specify the interface to use with the `--vcan` parameter. If the parameter is not specified, the script will use the first available can interface.


## Project structure
Server is the main controller of the project.
Server and Bot are asynchronous processes and communicate with each other using MQTT protocol. Therefore all parts of the project are independent and connected by MQTT.
![Project structure](assets/auto_ice_structure.png)[source](https://drive.google.com/file/d/1y8k6VckcmkdSaXO5kJmT2Wjp_cWLKK8U/view?usp=sharing)
### MQTT communication diagram
Server subscribes to bot and RPi topics and controls their interconnection.
Bot subscribes to its commander topic and sends user commands to the server.
Raspberry Pi subscribes to its commander topic and sends parsed dronecan messages to the server.
![MQTT communication diagram](assets/mqtt_diagram.svg)[source](https://drive.google.com/file/d/101-VWQ6xDPb7unSD5HLtugVJ_l3K8BXP/view?usp=sharing)


# TODO:
- [ ] Maybe split ExceedanceTracker responsibility to Modes
## Tests
- [ ] Add tests for bot
- [ ] Add tests for server
Extend tests for client:
    - [ ] Test on NOT_CONNECTED state after successful connection to exteranl node

## Hints
For fast mqtt server setup, edit the file `/etc/mosquitto/mosquitto.conf` and add the following lines:
```
allow_anonymous true
listener 1883 0.0.0.0
protocol mqtt
```

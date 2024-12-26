# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

sudo apt update && sudo apt upgrade
sudo apt-get install python-rpi.gpio python3-rpi.gpio
sudo apt install -y mosquitto mosquitto-clients
sudo systemctl enable mosquitto.service
sudo systemctl restart mosquitto
sudo chmod +x ./raspberry/create_slcan.sh
sudo ./raspberry/create_slcan.sh

#!/usr/bin/env bash
# used pipeline from https://santoshk.dev/posts/2023/mqtt-basics-and-how-to-get-started-on-ubuntu/
apt-get update
apt-get install curl gnupg2 wget git apt-transport-https ca-certificates -y
add-apt-repository ppa:mosquitto-dev/mosquitto-ppa -y
apt install mosquitto mosquitto-clients -y
sudo systemctl restart mosquitto

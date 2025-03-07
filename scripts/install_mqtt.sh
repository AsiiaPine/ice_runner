#!/usr/bin/env bash
# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>
# used pipeline from https://santoshk.dev/posts/2023/mqtt-basics-and-how-to-get-started-on-ubuntu/


#check OS version
if [ -f /etc/os-release ]; then
    # freedesktop.org and systemd
    . /etc/os-release
    OS=$NAME
    VER=$ID
elif type lsb_release >/dev/null 2>&1; then
    # linuxbase.org
    OS=$(lsb_release -si)
    VER=$(lsb_release -sr)
elif [ -f /etc/lsb-release ]; then
    # For some versions of Debian/Ubuntu without lsb_release command
    . /etc/lsb-release
    OS=$DISTRIB_ID
    VER=$DISTRIB_RELEASE
elif [ -f /etc/debian_version ]; then
    # Older Debian/Ubuntu/etc.
    OS=Debian
    VER=$(cat /etc/debian_version)
else
    # Fall back to uname, e.g. "Linux <version>", also works for BSD, etc.
    OS=$(uname -s)
    VER=$(uname -r)
fi

echo "Installing MQTT server"
if [ "$OS" = "Ubuntu" ]; then
    apt update && apt upgrade -y
    apt install -y mosquitto mosquitto-clients
elif [ "$OS" = "Manjaro Linux" ]; then
    pacman -S mosquitto
else
    echo "Unsupported OS"
    exit 1
fi

systemctl enable mosquitto.service
systemctl restart mosquitto


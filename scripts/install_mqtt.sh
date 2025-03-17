#!/usr/bin/env bash
# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>
# used pipeline from https://santoshk.dev/posts/2023/mqtt-basics-and-how-to-get-started-on-ubuntu/


#check OS version
if [ -f /etc/lsb-release ]; then
    # For some versions of Debian/Ubuntu without lsb_release command
    . /etc/lsb-release
    OS=$DISTRIB_ID
    VER=$DISTRIB_RELEASE
    echo "OS: $OS"
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
    sudo apt update && apt upgrade -y
    sudo apt install -y mosquitto mosquitto-clients
elif [ "$OS" = "ManjaroLinux" ]; then
    sudo pacman -S mosquitto
else
    echo "Unsupported OS"
    exit 1
fi

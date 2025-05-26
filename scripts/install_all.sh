#!/usr/bin/env bash
# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
$SCRIPT_DIR/install_mqtt.sh

if [[ $? -eq 1 ]]; then
    echo "Error installing MQTT server"
    exit 1
fi

$SCRIPT_DIR/prepare_python.sh

if [[ $? -eq 1 ]]; then
    echo "Error installing python dependencies"
    exit 1
fi

echo "Done!"

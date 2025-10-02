#!/usr/bin/env bash
# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
PARENT_DIR=$(dirname $SCRIPT_DIR)

# change the peth in the service file to the correct path
sed -i "s|CURRENT_DIR|$PARENT_DIR|g" $PARENT_DIR/ice_runner.service

echo $(cat $PARENT_DIR/ice_runner.service)

echo "Creating systemd service..."

sudo cp $PARENT_DIR/ice_runner.service /etc/systemd/system/ice_runner.service
systemctl daemon-reload
systemctl --user enable ice_runner.service
systemctl --user start ice_runner.service

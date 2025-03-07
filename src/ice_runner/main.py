#!/usr/bin/env python3
# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import argparse
import os.path

script_dir = os.path.dirname(os.path.realpath(__file__))

parser = argparse.ArgumentParser()
parser.add_argument('command', choices=['bot', 'sim', 'client', 'srv'])
parser.add_argument('--log_dir', default=script_dir)
command, rem = parser.parse_known_args()

if command.command == 'bot':
    from bot.main import start
    start(command.log_dir, rem)

elif command.command == 'sim':
    from ice_sim.simple_sim import start
    start(rem)

elif command.command == 'client':
    from raspberry.main import start
    start(command.log_dir, rem)

elif command.command == 'srv':
    from server.main import start
    start(command.log_dir, rem)

"""This module contains the RunnerState class"""

# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

from enum import IntEnum

class RunnerState(IntEnum):
    NOT_CONNECTED=-1
    RUNNING=0
    STARTING=1
    STOPPED=2
    STOPPING=3
    FAULT=4

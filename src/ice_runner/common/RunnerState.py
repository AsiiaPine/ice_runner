"""This module contains the RunnerState class"""

# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

from enum import IntEnum
import logging
import time

from common.ICEState import EngineState

class RunnerState(IntEnum):
    NOT_CONNECTED=-1
    RUNNING=0
    STARTING=1
    STOPPED=2
    STOPPING=3
    FAULT=4
    @classmethod
    def has_value(cls, value):
        return value in cls._value2member_map_
    @classmethod
    def get_values(cls):
        return cls._value2member_map_.values()

class RunnerStateController:
    """The class is used to control the state of the Runner"""
    def __init__(self) -> None:
        self.state = RunnerState.NOT_CONNECTED
        self.prev_state = RunnerState.NOT_CONNECTED
        self.prev_waiting_state_time = 0
        self.start_attempts = 0

    def update(self, ice_state: EngineState) -> None:
        """The function updates the state of the Runner"""
        self.prev_state = self.state
        if ice_state == EngineState.NOT_CONNECTED:
            logging.warning("NOT_CONNECTED\t-\tNo ICE connected")
            self.state = RunnerState.NOT_CONNECTED
            return

        if self.state == RunnerState.NOT_CONNECTED:
            self.state = RunnerState.STOPPED

        if self.state in (RunnerState.STOPPING, RunnerState.NOT_CONNECTED):
            if ice_state == EngineState.STOPPED:
                self.state = RunnerState.STOPPED
                logging.info("STOP\t-\tRunner stopped")
                return

        if self.state == RunnerState.STARTING:
            prev_waiting = self.prev_waiting_state_time
            if prev_waiting == 0:
                self.prev_waiting_state_time = time.time()
                return
            if ice_state == EngineState.WAITING and \
                        self.prev_waiting_state_time + 4 < time.time():
                self.prev_waiting_state_time = time.time()
                logging.info("STARTING\t-\tReceived waiting state")
                return
            if ice_state == EngineState.RUNNING\
                    and time.time() - prev_waiting > 4\
                    and self.prev_waiting_state_time > 0:
                print( time.time_ns() - prev_waiting, 4, prev_waiting, time.time())
                logging.info("STARTING\t-\tStarted successfully")
                self.state = RunnerState.RUNNING
                self.prev_waiting_state_time = 0
                return
            if ice_state == EngineState.STOPPED:
                return

        if self.state == RunnerState.RUNNING:
            if ice_state == EngineState.WAITING:
                self.state = RunnerState.STARTING
                self.start_attempts +=1
                self.prev_waiting_state_time = time.time()

                logging.info("RUNNING\t-\tReceived waiting state")
                return
            if ice_state == EngineState.RUNNING:
                return
            if ice_state == EngineState.STOPPED:
                self.state = RunnerState.STARTING
                self.start_attempts +=1
                logging.info("RUNNING\t-\tRunner stopped")
                return

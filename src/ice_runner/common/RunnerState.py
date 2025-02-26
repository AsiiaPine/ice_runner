"""This module contains the RunnerState class"""

# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

from enum import IntEnum
import logging
import time

from ice_runner.common.ICEState import RecipState

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

    def update(self, ice_state: RecipState) -> None:
        """The function updates the state of the Runner"""
        self.prev_state = self.state
        if ice_state == RecipState.NOT_CONNECTED:
            logging.warning("NOT_CONNECTED\t-\tNo ICE connected")
            self.state = RunnerState.NOT_CONNECTED
            return

        if ice_state == RecipState.STOPPED:
            if self.state in (RunnerState.STOPPING, RunnerState.NOT_CONNECTED):
                self.state = RunnerState.STOPPED
                logging.info("STOP\t-\tRunner stopped")
                return

            if self.state == RunnerState.RUNNING:
                self.state = RunnerState.STARTING
                logging.info("STARTING\t-\ICE stopped, trying to start again")
 
        if ice_state == RecipState.WAITING and \
                        self.prev_waiting_state_time + 4 < time.time():
            self.prev_waiting_state_time = time.time()
            if self.prev_state == RunnerState.STOPPED:
                self.state = RunnerState.STARTING
                logging.info("STARTING\t-\tStarting")
                return
            self.state = RunnerState.STARTING
            logging.info("WAITING\t-\twaiting state")
            return

        if self.state > RunnerState.STARTING or ice_state == RecipState["FAULT"]:
            self.start_time = 0
            logging.debug("STATE\t-\t stopped, rp state %s ice state %s",
                          self.state.name, ice_state.name)
            return

        if self.state == RunnerState.STARTING:
            prev_waiting = self.prev_waiting_state_time
            if ice_state == RecipState.RUNNING\
                    and time.time() - prev_waiting > 4\
                    and self.prev_waiting_state_time > 0:
                print( time.time_ns() - prev_waiting, 4, prev_waiting, time.time())
                logging.info("STARTING\t-\tstarted successfully")
                self.state = RunnerState.RUNNING
                self.prev_waiting_state_time = 0
                return

"""This module contains the RunnerStatus class"""

# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import logging
import time

from common.RunnerState import RunnerState
from raspberry.can_control.EngineState import EngineState

class RunnerStateController:
    """The class is used to control the state of the Runner"""
    def __init__(self) -> None:
        self.state = RunnerState.NOT_CONNECTED
        self.prev_state = RunnerState.NOT_CONNECTED
        self.last_starter_run_time = 0
        self.start_attempts = 0

    def update(self, engine_state: EngineState) -> None:
        """The function updates the state of the Runner"""
        if engine_state == EngineState.NOT_CONNECTED:
            self.state = RunnerState.NOT_CONNECTED
            self.prev_state = self.state
            return

        if engine_state == EngineState.FAULT:
            self.state = RunnerState.FAULT
            self.prev_state = self.state
            return

        self.prev_state = self.state

        if self.state == RunnerState.NOT_CONNECTED:
            if engine_state == EngineState.STOPPED:
                self.state = RunnerState.STOPPED
                logging.info("NOT_CONNECTED\t-\tRunner stopped")
                return
            self.state = RunnerState.STOPPING
            logging.warning("NOT_CONNECTED\t-\tRunner is running, but state was not connected")
            return

        if self.state == RunnerState.STOPPED:
            self.start_attempts = 0
            self.last_starter_run_time = 0

            if engine_state != EngineState.STOPPED:
                self.state = RunnerState.STOPPING
                logging.warning("STOPPING\t-\tRunner is not stopped %s", engine_state.name)
            return

        if self.state == RunnerState.STOPPING:
            if engine_state == EngineState.STOPPED:
                self.state = RunnerState.STOPPED
                self.start_attempts = 0

                logging.info("STOP\t-\tRunner stopped")
            return

        if self.state == RunnerState.STARTING:
            last_starter_run_time = self.last_starter_run_time
            if last_starter_run_time == 0:
                self.last_starter_run_time = time.time()
                return

            if engine_state == EngineState.STARTER_RUNNING and \
                        last_starter_run_time + 4 < time.time():
                self.start_attempts +=1
                self.last_starter_run_time = time.time()
                logging.info("STARTING\t-\tReceived waiting state")
                return

            if engine_state == EngineState.STARTER_WAITING\
                    and time.time() - last_starter_run_time > 4\
                    and last_starter_run_time > 0:
                logging.info("STARTING\t-\tStarted successfully")
                self.state = RunnerState.RUNNING
                return

            if engine_state == EngineState.STOPPED:
                return

        if self.state == RunnerState.RUNNING:
            if engine_state == EngineState.STARTER_RUNNING:
                self.state = RunnerState.STARTING
                self.last_starter_run_time = time.time()

                logging.info("RUNNING\t-\tReceived waiting state")
                return
            if engine_state == EngineState.STARTER_WAITING:
                return
            if engine_state == EngineState.STOPPED:
                self.state = RunnerState.STARTING
                self.start_attempts +=1
                logging.info("RUNNING\t-\tRunner stopped")
                return

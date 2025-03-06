# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import logging
import time
from common.RunnerState import RunnerState
from raspberry.can_control.EngineState import EngineStatus
from raspberry.can_control.RunnerConfiguration import RunnerConfiguration
from raspberry.can_control.RunnerStateController import RunnerStateController
from raspberry.can_control.modes import ICERunnerMode


class ExceedanceTracker:
    """The class is used to track the excedance of the conditions"""
    def __init__(self) -> None:
        self.temp: bool = False
        self.vin: bool = False
        self.vibration: bool = False
        self.time: bool = False
        self.fuel_level: bool = False
        self.start_attempts: bool = False
        self.rpm: bool = False
        self.max_rpm: bool = False

    def check_not_started(self, state: EngineStatus) -> bool:
        """The function checks conditions when the ICE is not started"""
        eng_time_ex = False
        if state.engaged_time is not None:
            eng_time_ex = state.engaged_time > 40 * 60 * 60 # 40 hours
            if eng_time_ex:
                logging.warning("STATUS\t-\tEngaged time %d is exeeded", state.engaged_time)
        if self.vin or self.temp or eng_time_ex:
            logging.warning(f"STATUS\t-\tFlags exceeded:\n\
                            vin {self.vin}\n\
                            temp {self.temp}\n\
                            engaged time {eng_time_ex}\n\
                            fuel level {self.fuel_level}")
        return bool(sum([self.vin, self.temp, eng_time_ex, self.fuel_level]))

    def cleanup(self):
        """The function cleans up the ICE state"""
        dictionary = vars(self)
        for key in dictionary:
            dictionary[key] = False

    def check_mode_specialized(self, state: EngineStatus, configuration: RunnerConfiguration,
                               start_time: float, state_controller: RunnerStateController) -> None:
        """The function checks conditions when the ICE is in specialized mode"""

        if configuration.mode == ICERunnerMode.CHECK:
            #   last 12 seconds
            self.time = start_time > 0 and\
                                    12 < time.time() - start_time
            return

        if configuration.mode == ICERunnerMode.FUEL_PUMPTING:
            #   last 30 seconds
            self.time = start_time > 0 and\
                                    30 < time.time() - start_time
            return

        self.time = start_time > 0 and time.time() - start_time > configuration.time

        if state_controller.state == RunnerState.STARTING:
            return

        if configuration.mode == ICERunnerMode.CONST:
            self.rpm = False
            return

        if configuration.mode == ICERunnerMode.PID:
            self.rpm = not(configuration.rpm - 500 < state.rpm < configuration.rpm + 500)
            return

        if configuration.mode == ICERunnerMode.RPM:
            # the mode is not supported yet
            return


    def check_running(self, state: EngineStatus, configuration: RunnerConfiguration,
                        start_time: float, state_controller: RunnerStateController) -> bool:
        """The function checks conditions when the ICE is running"""
        if state.rpm > 7500:
            logging.warning(f"STATUS\t-\tRPM exceeded {state.rpm}, 7500")
            self.max_rpm = True

        if state_controller.start_attempts > configuration.start_attemts:
            logging.warning(
                f"STATUS\t-\tStart attempts exceeded {state_controller.start_attempts},\
                {configuration.start_attemts}")
            self.start_attempts = True
            return True

        self.check_mode_specialized(state, configuration, start_time, state_controller)
        self.fuel_level = configuration.min_fuel_volume > state.fuel_level_percent
        self.temp = configuration.max_temperature < state.temp

        self.vibration = state.rec_imu and\
                                    configuration.max_vibration < state.vibration
        flags_attr = vars(self)
        if sum(flags_attr[name] for name in flags_attr.keys() if flags_attr[name]) > 0:
            logging.warning(f"STATUS\t-\tFlags exceeded:\n{vars(self)}")
        return bool(sum(flags_attr[name] for name in flags_attr.keys() if flags_attr[name]))

    def check(self, state: EngineStatus, configuration: RunnerConfiguration,
                                state_controller: RunnerStateController, start_time: float) -> bool:
        """The function analyzes the conditions of the ICE runner and returns
        if any Configuration parameters were exceeded. Returns 0 if no conditions were exceeded,
        1 if conditions were exceeded."""
        self.vin = configuration.min_vin_voltage > state.voltage_in
        self.temp = configuration.max_temperature < state.temp
        self.fuel_level = configuration.min_fuel_volume > state.fuel_level_percent
        if state_controller.state == RunnerState.STOPPED:
            assert state_controller.start_attempts == 0, f"{state_controller.state.name}\
                {state_controller.start_attempts}"
            return self.check_not_started(state)

        return self.check_running(state, configuration, start_time, state_controller)

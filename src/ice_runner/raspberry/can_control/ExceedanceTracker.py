# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import logging
import time
from common.RunnerState import RunnerState
from raspberry.can_control.EngineState import EngineStatus
from raspberry.RunnerConfiguration import RunnerConfiguration
from raspberry.can_control.RunnerStateController import RunnerStateController
from raspberry.can_control.modes import ICERunnerMode

RPM_CONTROL_TOLERANCE = 500

class ExceedanceTracker:
    _latest_status = None
    _latest_configurator = None
    _latest_state_controller = None
    """The class is used to track the exceedance of the conditions"""
    def __init__(self) -> None:
        # Fault flags:
        self.temp: bool = False
        self.vin: bool = False
        self.fuel_level: bool = False
        self.vibration: bool = False
        self.rpm: bool = False
        self.max_rpm: bool = False
        self.start_attempts: bool = False

        # Successful completion flags:
        self.time: bool = False

    def is_exceeded_check(self, state: EngineStatus,
                    configuration: RunnerConfiguration,
                    state_controller: RunnerStateController,
                    start_time: float) -> bool:
        """
        The function analyzes the conditions of the ICE runner and returns
        if any Configuration parameters were exceeded. Returns 0 if no conditions were exceeded,
        1 if conditions were exceeded.
        """
        ExceedanceTracker._latest_status = state
        ExceedanceTracker._latest_configurator = configuration
        ExceedanceTracker._latest_state_controller = state_controller

        if configuration.max_temperature != 0:
            self.temp = configuration.max_temperature < state.temp
        self.vin = configuration.min_vin_voltage > state.voltage_in
        self.fuel_level = configuration.min_fuel_volume > state.fuel_level_percent
        if state_controller.state == RunnerState.STOPPED:
            assert state_controller.start_attempts == 0, f"{state_controller.state.name}\
                {state_controller.start_attempts}"
            return self.check_not_started(state)

        return self.check_running(state, configuration, start_time, state_controller)

    def get_text_description(self):
        emergency_stop_reasons = ""

        if self.temp:
            actual_temperature_c = round(ExceedanceTracker._latest_status.temp - 273.15)
            max_temperature_c = round(ExceedanceTracker._latest_configurator.max_temperature - 273.15)
            emergency_stop_reasons += f"Temperature {actual_temperature_c}°C more than ({max_temperature_c}°C)\n"

        if self.vin:
            actual_vin = round(ExceedanceTracker._latest_status.voltage_in)
            min_vin = round(ExceedanceTracker._latest_configurator.min_vin_voltage)
            emergency_stop_reasons += f"Vin: {actual_vin} less than {min_vin}\n"

        if self.fuel_level:
            actual_fuel_level = round(ExceedanceTracker._latest_status.fuel_level_percent)
            min_fuel_level = round(ExceedanceTracker._latest_configurator.min_fuel_volume)
            emergency_stop_reasons += f"Fuel: {actual_fuel_level} less than {min_fuel_level}\n"

        if self.vibration:
            pass # not supported at the moment

        if self.rpm:
            actual_rpm = round(ExceedanceTracker._latest_status.rpm)
            max_rpm = round(ExceedanceTracker._latest_configurator.rpm) + RPM_CONTROL_TOLERANCE
            emergency_stop_reasons += f"RPM: {actual_rpm} exceed the control tolerance range ({max_rpm})\n"

        if self.max_rpm:
            actual_rpm = round(ExceedanceTracker._latest_status.rpm)
            emergency_stop_reasons += f"RPM {actual_rpm} exceed max RPM ({ExceedanceTracker._latest_configurator.max_rpm})\n"

        if self.start_attempts:
            start_attemts = ExceedanceTracker._latest_configurator.start_attemts
            emergency_stop_reasons += f"Start attems exceeded {start_attemts}\n"

        if len(emergency_stop_reasons) > 0:
            return "Аварийная остановка:\n" + emergency_stop_reasons

        if not self.time:
            return "Неизвестная причина остановки"

        return "Обкатка успешно завершена по таймауту"

    def cleanup(self):
        """
        The function cleans up the ICE state
        """
        self.__init__()

    def check_not_started(self, state: EngineStatus) -> bool:
        """The function checks conditions when the ICE is not started"""
        eng_time_ex = False
        if state.engaged_time is not None:
            eng_time_ex = state.engaged_time > 40 * 60 * 60 # 40 hours

        if self.vin or self.temp or eng_time_ex:
            logging.warning(f"STATUS\t-\tFlags exceeded:\n\
                            vin {self.vin}\n\
                            temp {self.temp} ({state.temp})\n\
                            engaged time {eng_time_ex}\n\
                            fuel level {self.fuel_level}\n\
                            start attempts {self.start_attempts}")
        return bool(sum([self.vin, self.temp, eng_time_ex, self.fuel_level, self.start_attempts]))

    def check_running(self, state: EngineStatus,
                            configuration: RunnerConfiguration,
                            start_time: float,
                            state_controller: RunnerStateController) -> bool:
        """The function checks conditions when the ICE is running"""
        if state.rpm > configuration.max_rpm:
            logging.warning(
                    f"STATUS\t-\tRPM exceeded rpm_max value {state.rpm}, {configuration.max_rpm}")
            self.max_rpm = True

        self.check_mode_specialized(state, configuration, start_time, state_controller)
        self.fuel_level = configuration.min_fuel_volume > state.fuel_level_percent
        if configuration.max_temperature != 0:
            self.temp = configuration.max_temperature < state.temp

        self.vibration = state.rec_imu and\
                                    configuration.max_vibration < state.vibration
        flags_attr = vars(self)
        if sum(flags_attr[name] for name in flags_attr.keys() if flags_attr[name]) > 0:
            logging.warning(f"STATUS\t-\tFlags exceeded:\n{vars(self)}")
        return bool(sum(flags_attr[name] for name in flags_attr.keys() if flags_attr[name]))

    def check_mode_specialized(self, state: EngineStatus,
                                     configuration: RunnerConfiguration,
                                     start_time: float,
                                     state_controller: RunnerStateController) -> None:
        """The function checks conditions when the ICE is in specialized mode"""

        if configuration.mode == ICERunnerMode.FUEL_PUMPTING:
            #   last 30 seconds
            self.time = start_time > 0 and\
                                    30 < time.time() - start_time
            return

        if state_controller.start_attempts > configuration.start_attemts:
            logging.warning(
                f"STATUS\t-\tStart attempts exceeded {state_controller.start_attempts},\
                {configuration.start_attemts}")
            self.start_attempts = True

        if configuration.mode == ICERunnerMode.CHECK:
            #   last 12 seconds
            self.time = start_time > 0 and\
                                    12 < time.time() - start_time
            return


        self.time = start_time > 0 and time.time() - start_time > configuration.time

        if state_controller.state == RunnerState.STARTING:
            return

        if configuration.mode == ICERunnerMode.CONST:
            self.rpm = False
            return

        if configuration.mode == ICERunnerMode.PID:
            if state_controller.state == RunnerState.RUNNING and time.time() - start_time > 3:
                self.rpm = state.rpm > configuration.rpm + RPM_CONTROL_TOLERANCE
            return

        if configuration.mode == ICERunnerMode.RPM:
            # the mode is not supported yet
            return

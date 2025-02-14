"""The module is used to control the engine running-in. 
    The engine should be connected to the raspberry pi via DroneCAN"""

# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import asyncio
import datetime
import os
import time
import logging
import traceback
from enum import IntEnum
from typing import Dict
from mqtt.handlers import MqttClient
from can_control.node import (
    CanNode, start_dronecan_handlers, ICE_THR_CHANNEL, ICE_AIR_CHANNEL)
from common.ICEState import ICEState, RecipState
from common.RunnerState import RunnerState
from common.IceRunnerConfiguration import IceRunnerConfiguration

if os.path.exists("/proc/device-tree/model"):
    from RPi import GPIO # Import Raspberry Pi GPIO library

START_STOP_PIN = 24
RESISTOR_PIN = 23

if os.path.exists("/proc/device-tree/model"):
    # GPIO setup
    GPIO.setwarnings(True) # Ignore warning for now
    GPIO.setmode(GPIO.BCM) # Use physical pin numbering
    # Setup CAN terminator
    GPIO.setup(RESISTOR_PIN, GPIO.OUT)
    GPIO.output(RESISTOR_PIN, GPIO.HIGH)

class ExceedanceTracker:
    """The class is used to track the excedance of the conditions"""
    def __init__(self) -> None:
        self.temp: bool = False
        self.vin: bool = False
        self.gas_throttle: bool = False
        self.air_throttle: bool = False
        self.vibration: bool = False
        self.time: bool = False
        self.fuel_level: bool = False
        self.start_attempts: bool = False

    def check_not_started(self, state: ICEState, configuration: IceRunnerConfiguration) -> bool:
        """The function checks conditions when the ICE is not started"""
        eng_time_ex = False
        if state.engaged_time is not None:
            eng_time_ex = state.engaged_time > 40 * 60 * 60 # 40 hours
            if eng_time_ex:
                logging.warning("STATUS\t-\tEngaged time %d is exeeded", state.engaged_time)
        if self.vin or self.temp or eng_time_ex:
            pass
            # logging.warning(f"STATUS\t-\tFlags exceeded:\n\
            #                 vin {self.vin}\n\
            #                 temp {self.temp}\n\
            #                 engaged time {eng_time_ex}")
        return sum([self.vin, self.temp, eng_time_ex])

    def cleanup(self):
        """The function cleans up the ICE state"""
        dictionary = vars(self)
        for key in dictionary:
            dictionary[key] = False

    def check_mode_specialized(self, state: ICEState, configuration: IceRunnerConfiguration,
                               start_time: float) -> bool:
        """The function checks conditions when the ICE is in specialized mode"""
        if configuration.mode < ICERunnerMode.RPM:
            self.time = start_time > 0 and time.time() - start_time > configuration.time
            air_in_bound = configuration.air_throttle - 15 < state.air_throttle\
                                                        < configuration.air_throttle + 15
            self.air_throttle = not air_in_bound

        if configuration.mode == ICERunnerMode.SIMPLE:
            self.time = start_time > 0 and time.time() - start_time > configuration.time
            gas_in_bound = configuration.gas_throttle - 15 < state.gas_throttle\
                                                        < configuration.gas_throttle + 15
            self.gas_throttle = not gas_in_bound
            air_in_bound = configuration.air_throttle - 15 < state.air_throttle\
                                                        < configuration.air_throttle + 15
            self.air_throttle = not air_in_bound
            self.rpm = False
            return sum([self.gas_throttle, self.air_throttle, self.time])

        if configuration.mode == ICERunnerMode.PID: 
            self.rpm = configuration.rpm - 1000 < state.rpm < configuration.rpm + 1000
            return sum([self.rpm, self.time])

        if configuration.mode == ICERunnerMode.RPM:
            # the mode is not supported yet
            return True

        if configuration.mode == ICERunnerMode.CHECK:
            #   last 8 seconds
            self.time = start_time > 0 and\
                                    8 < time.time() - start_time
        if configuration.mode == ICERunnerMode.FUEL_PUMPTING:
            #   last 60 seconds
            self.time = start_time > 0 and\
                                    60 < time.time() - start_time
        return self.time

    def check_running(self, state: ICEState, configuration: IceRunnerConfiguration,
                        start_time: float, runner_state: RunnerState) -> bool:
        """The function checks conditions when the ICE is running"""
        # the ICE is running, so check dynamic conditions
        if runner_state == RunnerState.STARTING:
            state.start_attempts += 1
            if state.start_attempts > configuration.start_attemts:
                logging.warning(f"STATUS\t-\tStart attempts exceeded")
                self.start_attempts = True
                return True
        self.check_mode_specialized(state, configuration, start_time)
        self.fuel_level = configuration.min_fuel_volume > state.fuel_level_percent
        self.temp = configuration.max_temperature < state.temp

        self.time = start_time > 0 and\
                                    configuration.time < time.time() - start_time
        self.vibration = state.rec_imu and\
                                    configuration.max_vibration < state.vibration
        flags_attr = vars(self)
        if sum(flags_attr[name] for name in flags_attr.keys() if flags_attr[name]):
            logging.warning(f"STATUS\t-\tFlags exceeded:\n\
                            vibration {self.vibration}\n\
                            time {self.time}\n\
                            gas throttle {self.gas_throttle}\
                                         {configuration.gas_throttle, state.gas_throttle}\n\
                            temp {self.temp}\n\
                            fuel level {self.fuel_level}")

        return sum(flags_attr[name] for name in flags_attr.keys() if flags_attr[name])

    def check(self, state: ICEState, configuration: IceRunnerConfiguration,
                                runner_state: RunnerState, start_time: float) -> bool:
        """The function analyzes the conditions of the ICE runner and returns
        if any Configuration parameters were exceeded. Returns 0 if no conditions were exceeded,
        1 if conditions were exceeded."""
        self.vin = configuration.min_vin_voltage > state.voltage_in
        self.temp = configuration.max_temperature < state.temp
        self.fuel_level = configuration.min_fuel_volume > state.fuel_level
        if start_time <= 0 or state.ice_state > RunnerState.STARTING:
            return self.check_not_started(state, configuration)

        return self.check_running(state, configuration, start_time, runner_state)

class ICERunnerMode(IntEnum):
    """The class is used to define the mode of the ICE runner"""
    SIMPLE = 0 # Юзер задает 30-50% тяги, и просто сразу же ее выставляем, без ПИД-регулятора.
                # Без проверки оборотов, но с проверкой температуры.
    PID = 1 # Юзер задает обороты, и мы их поддерживаем ПИД-регулятором на стороне скрипта.
    RPM = 2 # Команда на 4500 оборотов (RPMCommand) без ПИД-регулятора
                # на стороне скрипта - все на стороне платы.
    CHECK = 3 # Запуск на 8 секунд, проверка сартера
    FUEL_PUMPTING = 4 # Запуск на 60 секунд

class PIDController:
    """Basic PID controller"""

    def __init__(self, seeked_value: int) -> None:
        self.seeked_value = seeked_value
        self.coeffs: Dict[str, float] = {"kp": 0.0, "ki": 0.0, "kd": 0.0}
        self.prev_time = 0
        self.prev_error = 0
        self.integral = 0

    def get_pid_command(self, val: int) -> int:
        """The function calculates PID command"""
        dt = time.time() - self.prev_time
        error = self.seeked_value - val
        drpm = (error - self.prev_error) / dt
        self.integral += self.coeffs["ki"] * error * (dt)

        self.prev_time = time.time()
        self.prev_error = error
        diff_part = self.coeffs["kd"] * drpm
        int_part = self.coeffs["ki"] * self.integral
        pos_part = self.coeffs["kp"] * error
        return self.seeked_value + pos_part + diff_part + int_part

    def change_coeffs(self, coeffs: Dict[str, float]) -> None:
        """The function changes the coefficients of the PID controller"""
        self.coeffs = coeffs

class ICECommander:
    """The class is used to control the ICE runner"""
    def __init__(self, configuration: IceRunnerConfiguration = None) -> None:
        self.run_state: RunnerState = RunnerState.NOT_CONNECTED
        self.configuration: IceRunnerConfiguration = configuration
        self.ex_tracker: ExceedanceTracker = ExceedanceTracker()
        self.mode: ICERunnerMode = ICERunnerMode(configuration.mode)
        if self.mode == ICERunnerMode.PID:
            self.pid_controller: PIDController = PIDController(configuration.rpm)

        self.start_time: float = 0
        self.prev_state_report_time: float = 0
        self.prev_waiting_state_time: float = 0
        self.prev_report_time: float = 0
        self.last_button_cmd = 1

    def check_conditions(self) -> int:
        """The function analyzes the conditions of the ICE runner
            and returns if any Configuration parameters were exceeded.
            Returns 0 if no conditions were exceeded, 1 if conditions were exceeded."""
        return self.ex_tracker.check(CanNode.state, self.configuration,
                                     self.run_state, self.start_time)

    def set_command(self) -> None:
        """The function sets the command to the ICE node according to the current mode"""
        if self.run_state == RunnerState.NOT_CONNECTED or self.run_state > RunnerState.STARTING:
            CanNode.cmd.cmd = [0]* (ICE_AIR_CHANNEL + 1)
            CanNode.air_cmd.command_value = 0
            return

        if self.run_state == RunnerState.STARTING:
            CanNode.cmd.cmd[ICE_THR_CHANNEL] = 3500
            CanNode.air_cmd.command_value = 2000
            return

        if self.mode == ICERunnerMode.SIMPLE:
            CanNode.cmd.cmd[ICE_THR_CHANNEL] = self.configuration.rpm
            # self.dronecan_commander.cmd.cmd[ICE_AIR_CHANNEL] = MAX_AIR_OPEN
        elif self.mode == ICERunnerMode.PID:
            CanNode.cmd.cmd[ICE_THR_CHANNEL] = int(self.pid_controller.get_pid_command(
                                                                            CanNode.state.rpm))
            # self.dronecan_commander.cmd.cmd[ICE_AIR_CHANNEL] = MAX_AIR_OPEN
        elif self.mode == ICERunnerMode.RPM:
            CanNode.cmd.cmd[ICE_THR_CHANNEL] = self.configuration.rpm
            # self.dronecan_commander.cmd.cmd[ICE_AIR_CHANNEL] = MAX_AIR_OPEN

    def stop(self) -> None:
        """The function stops the ICE runner and resets the runner state"""
        self.run_state = RunnerState.STOPPING
        MqttClient.to_stop = 0
        CanNode.save_file()
        self.send_log()
        CanNode.change_file()
        self.start_time = 0
        self.ex_tracker.cleanup()

    def set_state(self, cond_exceeded: bool) -> None:
        """Analyzes engine state send with Reciprocating status and sets the runner state
            accordingly."""
        ice_state = CanNode.state.ice_state
        rpm = CanNode.state.rpm
        run_state = self.run_state

        if cond_exceeded and run_state in (RunnerState.STARTING, RunnerState.RUNNING):
            logging.info("STOP\t-\tconditions exceeded")
            logging.debug("STOP\t-\tconditions: %s", frozenset(vars(self.ex_tracker).items()))
            self.stop()
            MqttClient.publish_stop_reason(f"Conditions exceeded: {vars(self.ex_tracker)}")
            return

        if run_state > RunnerState.STARTING or ice_state == RecipState["FAULT"]:
            self.start_time = 0
            logging.debug("STATE\t-\t stopped, rp state %s ice state %s",
                          run_state.name, ice_state.name)
            return

        if run_state == RunnerState.STARTING:
            if time.time() - self.start_time > 30:
                self.run_state = RunnerState.STOPPING
                logging.error("STARTING\t-\tstart time exceeded")
                self.stop()
                return
            if ice_state == RecipState.RUNNING\
                    and rpm > 1500\
                    and time.time_ns() - self.prev_waiting_state_time > 3*10**9:
                logging.info("STARTING\t-\tstarted successfully")
                self.run_state = RunnerState.RUNNING
                self.prev_waiting_state_time = 0
                return

        if ice_state == RecipState.WAITING and \
                        self.prev_waiting_state_time + 3*10**9 < time.time_ns():
            self.prev_waiting_state_time = time.time_ns()
            self.run_state = RunnerState.STARTING
            logging.info("WAITING\t-\twaiting state")

    async def spin(self) -> None:
        """Main function called in loop"""
        self.report_status()
        ice_state = CanNode.state.ice_state
        self.check_mqtt_cmd()
        cond_exceeded = self.check_conditions()
        self.set_state(cond_exceeded)
        if ice_state == RecipState.NOT_CONNECTED:
            logging.warning("NOT_CONNECTED\t-\tNo ICE connected")
            self.run_state = RunnerState.NOT_CONNECTED
            CanNode.cmd.cmd = [0] * (ICE_THR_CHANNEL + 1)
            CanNode.spin()
            await asyncio.sleep(1)
            return

        if ice_state == RecipState.STOPPED:
            if self.run_state != RunnerState.STARTING:
                self.run_state = RunnerState.STOPPED
        # self.check_buttons()
        self.set_command()
        logging.debug(f"CMD\t-\t{list(CanNode.cmd.cmd)}")
        CanNode.spin()
        self.report_state()
        await asyncio.sleep(0.05)

    def report_state(self) -> None:
        """The function reports state to MQTT broker"""
        if time.time() - self.prev_state_report_time > 0.5:
            MqttClient.publish_state(self.run_state.value)
            self.prev_state_report_time = time.time()

    def report_status(self) -> None:
        """The function reports status to MQTT broker"""
        if self.prev_report_time + self.configuration.report_period < time.time():
            state_dict = CanNode.state.to_dict()
            if self.start_time > 0:
                state_dict["start_time"] = datetime.datetime.fromtimestamp(self.start_time)\
                                                            .strftime('%Y-%m-%d %H:%M:%S')
            else:
                state_dict["start_time"] = "not started"
            MqttClient.publish_state(self.run_state.value)
            MqttClient.publish_status(state_dict)
            MqttClient.publish_messages(CanNode.messages)
            self.prev_report_time = time.time()

    def check_buttons(self):
        """The function checks the state of the stop button"""
        stop_switch = GPIO.input(START_STOP_PIN)
        if self.last_button_cmd == stop_switch:
            return
        if stop_switch:
            if self.run_state in (RunnerState.STARTING, RunnerState.RUNNING):
                self.run_state = RunnerState.STOPPING
            logging.info("BUTTON\t  Button released, state: %s", {self.run_state.name})
        else:
            if self.run_state > RunnerState.STARTING:
                self.run_state = RunnerState.STARTING
                self.start_time = time.time()
            logging.info("BUTTON\t  Button pressed, state: %s", {self.run_state.name})
        self.last_button_cmd = stop_switch

    def check_mqtt_cmd(self):
        """The function checks if MQTT command is received"""
        if MqttClient.to_stop:
            self.run_state = RunnerState.STOPPING
            MqttClient.to_stop = 0
            self.stop()
            MqttClient.publish_stop_reason("Got stop command from MQTT")
            logging.info("MQTT\t-\tCOMMAND\t stop, state: %s", {self.run_state.name})
        if MqttClient.to_run:
            if self.run_state > RunnerState.STARTING:
                self.run_state = RunnerState.STARTING
                self.start_time = time.time()
            logging.info("MQTT\t-\tCOMMAND\t run, state: %s", {self.run_state.name})
            MqttClient.to_run = 0
        if MqttClient.conf_updated:
            self.configuration = MqttClient.configuration
            self.configuration.to_file()
            MqttClient.conf_updated = False
            logging.info("MQTT\t-\tCOMMAND\t configuration updated")

    def send_log(self) -> None:
        """The function starts new log files and sends logs to MQTT broker"""
        MqttClient.run_logs["candump"] = CanNode.candump_filename
        MqttClient.run_logs["output"] = CanNode.output_filename
        MqttClient.publish_log()
        logging.info("SEND\t-\tlog %s", CanNode.output_filename)

    async def run(self) -> None:
        """The function starts the ICE runner"""
        CanNode.connect()
        CanNode.change_file()
        MqttClient.run_logs["candump"] = CanNode.candump_filename
        MqttClient.run_logs["output"] = CanNode.output_filename
        start_dronecan_handlers()
        MqttClient.publish_full_configuration(self.configuration.get_original_dict())
        while True:
            try:
                await self.spin()
            except asyncio.CancelledError:
                self.on_keyboard_interrupt()
            except Exception as e:
                logging.error(f"{e}\n{traceback.format_exc()}")
                continue

    def on_keyboard_interrupt(self):
        """The function is called when KeyboardInterrupt is 
            received and inform MQTT server about the exception"""
        self.stop()
        MqttClient.publish_stop_reason("Received KeyboardInterrupt")
        raise asyncio.CancelledError

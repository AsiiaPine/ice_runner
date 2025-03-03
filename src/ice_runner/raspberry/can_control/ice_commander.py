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
from raspberry.mqtt.handlers import MqttClient
from raspberry.can_control.node import (
    CanNode, start_dronecan_handlers, ICE_THR_CHANNEL)
from raspberry.can_control.modes import BaseMode, ICERunnerMode
from common.ICEState import ICEState, RecipState
from common.RunnerState import RunnerState, RunnerStateController
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
        self.vibration: bool = False
        self.time: bool = False
        self.fuel_level: bool = False
        self.start_attempts: bool = False
        self.rpm: bool = False

    def check_not_started(self, state: ICEState) -> bool:
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

    def check_mode_specialized(self, state: ICEState, configuration: IceRunnerConfiguration,
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


    def check_running(self, state: ICEState, configuration: IceRunnerConfiguration,
                        start_time: float, state_controller: RunnerStateController) -> bool:
        """The function checks conditions when the ICE is running"""
        # the ICE is running, so check dynamic conditions
        if state_controller.state == RunnerState.STARTING\
             and state_controller.prev_state != RunnerState.STARTING:
            state.start_attempts += 1
            if state.start_attempts > configuration.start_attemts:
                logging.warning(f"STATUS\t-\tStart attempts exceeded {state.start_attempts}, {configuration.start_attemts}")
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

    def check(self, state: ICEState, configuration: IceRunnerConfiguration,
                                state_controller: RunnerStateController, start_time: float) -> bool:
        """The function analyzes the conditions of the ICE runner and returns
        if any Configuration parameters were exceeded. Returns 0 if no conditions were exceeded,
        1 if conditions were exceeded."""
        self.vin = configuration.min_vin_voltage > state.voltage_in
        self.temp = configuration.max_temperature < state.temp
        self.fuel_level = configuration.min_fuel_volume > state.fuel_level_percent
        if state_controller.state > RunnerState.STARTING:
            return self.check_not_started(state)

        return self.check_running(state, configuration, start_time, state_controller)

class ICECommander:
    """The class is used to control the ICE runner"""
    def __init__(self, configuration: IceRunnerConfiguration = None) -> None:
        self.configuration: IceRunnerConfiguration = configuration
        self.exceedance_tracker: ExceedanceTracker = ExceedanceTracker()
        mode: ICERunnerMode = ICERunnerMode(configuration.mode)
        self.mode: BaseMode = mode.get_mode_class(configuration)
        self.start_time: float = 0
        self.prev_state_report_time: float = 0
        self.prev_report_time: float = 0
        self.state_controller = RunnerStateController()

    async def run(self) -> None:
        """The function starts the ICE runner"""
        CanNode.connect()
        start_dronecan_handlers()
        CanNode.change_file()
        MqttClient.run_logs = CanNode.can_output_filenames
        MqttClient.run_logs["candump"] = CanNode.candump_filename
        MqttClient.publish_full_configuration(self.configuration.get_original_dict())
        while True:
            try:
                await self.spin()
            except asyncio.CancelledError:
                self.on_keyboard_interrupt()
            except Exception as e:
                logging.error(f"{e}\n{traceback.format_exc()}")
                continue

    def stop(self) -> None:
        """The function stops the ICE runner and resets the runner state"""
        self.state_controller.state = RunnerState.STOPPING
        MqttClient.to_stop = 0
        CanNode.save_file()
        self.send_log()
        CanNode.change_file()
        self.start_time = 0
        self.state_controller.prev_waiting_state_time = 0
        self.exceedance_tracker.cleanup()

    async def spin(self) -> None:
        """Main function called in loop"""
        CanNode.spin()
        self.report_status()
        if CanNode.last_message_receive_time + 2 < time.time():
            CanNode.state.ice_state = RecipState.NOT_CONNECTED
        ice_state = CanNode.state.ice_state
        self.check_mqtt_cmd()
        cond_exceeded = self.check_conditions()
        self.update_state(cond_exceeded)
        if ice_state == RecipState.NOT_CONNECTED:
            logging.warning("NOT_CONNECTED\t-\tNo ICE connected")
            await asyncio.sleep(1)
            return

        self.set_can_command()
        logging.debug(f"CMD\t-\t{list(CanNode.cmd.cmd)}")
        self.report_state()
        self.prev_state = self.state_controller
        if self.state_controller == RunnerState.STOPPED:
            self.exceedance_tracker.start_attempts = 0
        await asyncio.sleep(0.05)

    def on_keyboard_interrupt(self):
        """The function is called when KeyboardInterrupt is 
            received and inform MQTT server about the exception"""
        self.stop()
        MqttClient.publish_stop_reason("Received KeyboardInterrupt")
        raise asyncio.CancelledError

    def check_conditions(self) -> int:
        """The function analyzes the conditions of the ICE runner
            and returns if any Configuration parameters were exceeded.
            Returns 0 if no conditions were exceeded, 1 if conditions were exceeded."""
        return self.exceedance_tracker.check(CanNode.state, self.configuration,
                                     self.state_controller, self.start_time)

    def set_can_command(self) -> None:
        """The function sets the command to the ICE node according to the current mode"""
        command = self.mode.get_command(self.state_controller.state, rpm=CanNode.state.rpm)
        CanNode.cmd.cmd[ICE_THR_CHANNEL] = command[0]
        CanNode.air_cmd.command_value = command[1]

    def update_state(self, cond_exceeded: bool) -> None:
        """Analyzes engine state send with Reciprocating status and sets the runner state
            accordingly."""
        if cond_exceeded and (self.state_controller.state in
                                (RunnerState.STARTING, RunnerState.RUNNING)):
            MqttClient.publish_stop_reason(f"Conditions exceeded: {vars(self.exceedance_tracker)}")
            logging.info("STOP\t-\tconditions exceeded")
            self.stop()
            return
        self.state_controller.update(CanNode.state.ice_state)

    def report_state(self) -> None:
        """The function reports state to MQTT broker"""
        if time.time() - self.prev_state_report_time > 0.5:
            MqttClient.publish_state(self.state_controller.state)
            self.prev_state_report_time = time.time()

    def report_status(self) -> None:
        """The function reports status to MQTT broker"""
        if self.prev_report_time + self.configuration.report_period < time.time():
            state_dict = CanNode.state.to_dict()
            time_left = self.configuration.time + self.start_time - time.time()
            if self.start_time > 0:
                state_dict["start_time"] = datetime.datetime.fromtimestamp(self.start_time)\
                                                            .strftime('%Y-%m-%d %H:%M:%S')
                state_dict["time_left"] = time_left / 60.0
            else:
                state_dict["start_time"] = "not started"
                state_dict["time_left"] = "not started"
            MqttClient.publish_state(self.state_controller.state)
            MqttClient.publish_status(state_dict)
            MqttClient.publish_messages(CanNode.messages)
            self.prev_report_time = time.time()

    def check_buttons(self):
        """The function checks the state of the stop button"""
        raise NotImplementedError

    def check_mqtt_cmd(self):
        """The function checks if MQTT command is received"""
        if MqttClient.to_stop:
            self.state_controller.state = RunnerState.STOPPING
            MqttClient.to_stop = 0
            self.stop()
            MqttClient.publish_stop_reason("Got stop command from MQTT")
            logging.info("MQTT\t-\tCOMMAND\t stop, state: %s", {self.state_controller.state.name})
        if MqttClient.to_run:
            if self.state_controller.state > RunnerState.STARTING:
                self.state_controller.state = RunnerState.STARTING
                self.start_time = time.time()
            logging.info("MQTT\t-\tCOMMAND\t run, state: %s", {self.state_controller.state.name})
            MqttClient.to_run = 0
        if MqttClient.conf_updated:
            self.configuration = MqttClient.configuration
            self.configuration.to_file()
            if self.configuration.mode != self.mode.name:
                mode = ICERunnerMode(self.configuration.mode)
                self.mode: BaseMode = mode.get_mode_class(self.configuration)
                MqttClient.publish_stop_reason(f"Switched to new mode {self.mode.name.name}")
                self.stop()
            else:
                self.mode.update_configuration(self.configuration)
            MqttClient.conf_updated = False
            logging.info("MQTT\t-\tCOMMAND\t configuration updated")

    def send_log(self) -> None:
        """The function starts new log files and sends logs to MQTT broker"""
        MqttClient.run_logs = CanNode.can_output_filenames
        MqttClient.run_logs["candump"] = CanNode.candump_filename
        MqttClient.publish_log()
        logging.info("SEND\t-\tlogs")

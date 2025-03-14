"""The module is used to control the engine running-in. 
    The engine should be connected to the raspberry pi via DroneCAN"""

# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import asyncio
import copy
import datetime
import os
import time
import logging
import traceback
from raspberry.can_control.ExceedanceTracker import ExceedanceTracker
from raspberry.mqtt.handlers import MqttClient
from raspberry.can_control.node import (
    CanNode, start_dronecan_handlers, ICE_THR_CHANNEL)
from raspberry.can_control.modes import BaseMode, ICERunnerMode
from raspberry.can_control.EngineState import EngineState
from raspberry.can_control.RunnerStateController import RunnerStateController
from common.RunnerState import RunnerState
from raspberry.can_control.RunnerConfiguration import RunnerConfiguration
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

class ICECommander:
    """The class is used to control the ICE runner"""
    def __init__(self, configuration: RunnerConfiguration = None) -> None:
        self.configuration: RunnerConfiguration = configuration
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

        CanNode.start_dump()
        MqttClient.run_logs = copy.deepcopy(CanNode.can_output_filenames)

        MqttClient.run_logs["candump"] = CanNode.candump_filename
        MqttClient.publish_full_configuration(self.configuration.get_original_dict())
        while True:
            try:
                await self.spin()
            except asyncio.CancelledError:
                self.on_keyboard_interrupt()
            except KeyboardInterrupt:
                self.on_keyboard_interrupt()
                raise asyncio.CancelledError
            except Exception as e:
                logging.error(f"{e}\n{traceback.format_exc()}")
                continue

    def stop(self) -> None:
        """The function stops the ICE runner and resets the runner state"""
        self.state_controller.state = RunnerState.STOPPING
        MqttClient.to_stop = 0
        self.start_time = 0

    async def spin(self) -> None:
        """Main function called in loop"""
        CanNode.spin()
        self.report_status()
        if CanNode.last_message_receive_time + 2 < time.time():
            CanNode.status.state = EngineState.NOT_CONNECTED
        engine_state = CanNode.status.state
        self.check_mqtt_cmd()
        cond_exceeded = self.check_conditions()
        self.update_state(cond_exceeded)
        if engine_state == EngineState.NOT_CONNECTED:
            logging.warning("NOT_CONNECTED\t-\tNo ICE connected")
            await asyncio.sleep(1)
            return
        if self.state_controller.state == RunnerState.STOPPED:
            self.exceedance_tracker.cleanup()
        self.set_can_command()
        self.report_state()
        self.prev_state = self.state_controller
        await asyncio.sleep(0.2)

    def on_keyboard_interrupt(self):
        """The function is called when KeyboardInterrupt is 
            received and inform MQTT server about the exception"""
        self.stop()
        CanNode.stop_dump()
        MqttClient.publish_stop_reason("Received KeyboardInterrupt")
        self.send_log()
        raise asyncio.CancelledError

    def check_conditions(self) -> int:
        """The function analyzes the conditions of the ICE runner
            and returns if any Configuration parameters were exceeded.
            Returns 0 if no conditions were exceeded, 1 if conditions were exceeded."""
        return self.exceedance_tracker.check(CanNode.status, self.configuration,
                                     self.state_controller, self.start_time)

    def set_can_command(self) -> None:
        """The function sets the command to the ICE node according to the current mode"""

        command = self.mode.get_command(self.state_controller.state,
                                        rpm=CanNode.status.rpm,
                                        engine_state=CanNode.status.state)
        CanNode.cmd.cmd[ICE_THR_CHANNEL] = command[0]
        CanNode.air_cmd.command_value = command[1]

    def update_state(self, cond_exceeded: bool) -> None:
        """Analyzes engine state send with Reciprocating status and sets the runner state
            accordingly."""
        if cond_exceeded and (self.state_controller.state in
                                (RunnerState.STARTING, RunnerState.RUNNING)):
            MqttClient.publish_stop_reason(self.exceedance_tracker.get_text_description())
            logging.info("STOP\t-\tconditions exceeded")
            self.stop()
            return

        if CanNode.status.state == EngineState.NOT_CONNECTED and\
                                    self.state_controller.prev_state != RunnerState.NOT_CONNECTED:
            logging.warning("%s\t-\tEngine disconnected", self.state_controller.prev_state.name)
            MqttClient.publish_stop_reason("Engine Disconnected!")
            self.stop()
            self.send_log()
            CanNode.start_dump()

        self.state_controller.update(CanNode.status.state)
        CanNode.status.start_attempts = self.state_controller.start_attempts
        if self.state_controller.state == RunnerState.STOPPED\
            and self.state_controller.prev_state == RunnerState.STOPPING:
            CanNode.stop_dump()
            self.send_log()
            CanNode.start_dump()

    def report_state(self) -> None:
        """The function reports state to MQTT broker"""
        if time.time() - self.prev_state_report_time > 0.5:
            MqttClient.publish_state(self.state_controller.state)
            self.prev_state_report_time = time.time()
            # logging.info(f"CMD\t-\t{list(CanNode.cmd.cmd)}")

    def report_status(self) -> None:
        """The function reports status to MQTT broker"""
        if self.prev_report_time + self.configuration.report_period < time.time():
            status_dict = CanNode.status.get_description_dict()
            time_left = self.configuration.time + self.start_time - time.time()
            if self.start_time > 0:
                status_dict["Time left"] = f"{round(time_left / 60, 1)} min"
            else:
                status_dict["Time left"] = "not started"
            MqttClient.publish_state(self.state_controller.state)
            MqttClient.publish_status(status_dict)
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
        MqttClient.run_logs = copy.deepcopy(CanNode.can_output_filenames)
        MqttClient.run_logs["candump"] = CanNode.candump_filename
        MqttClient.publish_log()
        logging.info("SEND\t-\tlogs")

#!/usr/bin/env python3
# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import asyncio
import datetime
from enum import IntEnum
import os
import time
import traceback
from node import CanNode, start_dronecan_handlers, MAX_AIR_OPEN, ICE_THR_CHANNEL, ICE_AIR_CHANNEL
from common.ICEState import ICEState, RecipFlags
from common.RPStates import RPFlags
from common.IceRunnerConfiguration import IceRunnerConfiguration
from mqtt_client import RaspberryMqttClient
import logging

logger = logging.getLogger(__name__)

if (os.path.exists("/proc/device-tree/model")):
    rpi_model = os.popen('cat /proc/device-tree/model').read()
    # GPIO setup
    import RPi.GPIO as GPIO # Import Raspberry Pi GPIO library
    GPIO.setwarnings(True) # Ignore warning for now
    GPIO.setmode(GPIO.BCM) # Use physical pin numbering
    start_stop_pin = 24
    # Setup CAN terminator
    resistor_pin = 23
    GPIO.setup(resistor_pin, GPIO.OUT)
    GPIO.output(resistor_pin, GPIO.HIGH)

    GPIO.setup(start_stop_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # Start/Stop button

class ExceedanceTracker:
    def __init__(self) -> None:
        self.throttle: bool = False
        self.temp: bool = False
        self.rpm: bool = False
        self.vin: bool = False
        self.vibration: bool = False
        self.time: bool = False
        self.rpm_min: bool = False

class ICERunnerMode(IntEnum):
    SIMPLE = 0 # Юзер задает 30-50% тяги, и просто сразу же ее выставляем, без ПИД-регулятора. Без проверки оборотов, но с проверкой температуры.
    PID = 1 # Юзер задает обороты, и мы их поддерживаем ПИД-регулятором на стороне скрипта.
    RPM = 2 # Команда на 4500 оборотов (RPMCommand) без ПИД-регулятора на стороне скрипта - все на стороне платы.

class PIDController:
    def __init__(self, seeked_value: int) -> None:
        self.seeked_value = seeked_value
        self.kp = 0.2
        self.ki = 0.0
        self.kd = 0.2
        self.error = 0
        self.prev_time = 0
        self.drpm = 0
        self.prev_error = 0
        self.integral = 0

    def get_pid_command(self, val: int) -> int:
        dt = time.time() - self.prev_time
        self.error = self.seeked_value - val 
        self.drpm = (self.error - self.prev_error) / dt
        self.integral += self.ki*self.error* (dt)

        self.prev_time = time.time()
        self.prev_error = self.error
        print(self.seeked_value, val, self.kp*self.error, self.kd*self.drpm, self.ki * self.integral)
        return self.seeked_value + self.kp*self.error + self.kd*self.drpm + self.ki * self.integral

class ICECommander:
    def __init__(self, reporting_period: float = 1, configuration: IceRunnerConfiguration = None) -> None:
        self.rp_state: RPFlags = RPFlags.NOT_CONNECTED
        self.reporting_period: float = reporting_period
        self.node: CanNode = CanNode()
        self.node.connect()
        self.configuration: IceRunnerConfiguration = configuration
        self.ex_tracker: ExceedanceTracker = ExceedanceTracker()
        self.mode: ICERunnerMode = ICERunnerMode(configuration.mode)

        self.start_time: float = 0
        self.prev_waiting_state_time: float = 0
        self.prev_report_time: float = 0
        self.prev_state_report_time: float = 0
        if self.mode == ICERunnerMode.PID:
            self.pid_controller: PIDController = PIDController(configuration.rpm)
        self.last_button_cmd = 1
        start_dronecan_handlers()

    async def run_candump(self) -> None:
        self.candump_task = asyncio.create_task(CanNode.run_candump())

    def check_conditions(self) -> int:
        # check if conditions are exeeded
        state = self.node.state
        if state.ice_state == RecipFlags.NOT_CONNECTED:
            self.rp_state = RPFlags.NOT_CONNECTED
            logger.warning("STATUS\t-\tice not connected")
            return 0
        if time.time() - CanNode.last_message_receive_time > 1:
            logging.critical("STATUS\t-\tToo long time without messages")
            CanNode.state = ICEState()
        if self.start_time <= 0 or state.ice_state > RPFlags.STARTING:
            self.ex_tracker.vin = self.configuration.min_vin_voltage > state.voltage_in
            self.ex_tracker.temp = self.configuration.max_temperature < state.temp
            eng_time_ex = False
            if state.engaged_time is not None:
              eng_time_ex = state.engaged_time > 40 * 60 * 60 # 40 hours
              if eng_time_ex:
                  logger.warning(f"STATUS\t-\tEngaged time {state.engaged_time} is exeeded")
            if self.ex_tracker.vin or self.ex_tracker.temp or eng_time_ex:
                logger.warning(f"STATUS\t-\tFlags exceeded: vin {self.ex_tracker.vin} temp {self.ex_tracker.temp} engaged time {eng_time_ex}")
            return sum([self.ex_tracker.vin, self.ex_tracker.temp,eng_time_ex])
        if self.rp_state == RPFlags.RUNNING:
            self.ex_tracker.rpm_min = 100 > state.rpm
        else:
            self.ex_tracker.rpm_min = False
        if self.configuration.min_fuel_volume < 100:
            self.fuel_level_ex = self.configuration.min_fuel_volume > state.fuel_level_percent
        else:
            self.fuel_level_ex = self.configuration.min_fuel_volume > state.fuel_level

        self.ex_tracker.throttle = self.configuration.max_gas_throttle < state.throttle
        self.ex_tracker.temp = self.configuration.max_temperature < state.temp
        self.ex_tracker.rpm = self.configuration.rpm  + 1000 < state.rpm
        self.ex_tracker.time = self.start_time > 0 and self.configuration.time < time.time() - self.start_time
        self.ex_tracker.vibration = self.node.has_imu and self.configuration.max_vibration < state.vibration
        flags_attr = vars(self.ex_tracker)
        if self.ex_tracker.vibration or self.ex_tracker.time or self.ex_tracker.rpm or self.ex_tracker.throttle or self.ex_tracker.temp or self.fuel_level_ex or self.ex_tracker.rpm_min:
            logger.warning(f"STATUS\t-\tFlags exceeded: vibration {self.ex_tracker.vibration} time {self.ex_tracker.time} rpm {self.ex_tracker.rpm}: {self.configuration.rpm, state.rpm} throttle {self.ex_tracker.throttle} temp {self.ex_tracker.temp} fuel level {self.fuel_level_ex} rpm min {self.ex_tracker.rpm_min}")
        return sum([flags_attr[name] for name in flags_attr.keys() if flags_attr[name]])

    def set_command(self) -> None:
        if self.rp_state == RPFlags.NOT_CONNECTED or self.rp_state > RPFlags.STARTING:
            self.node.cmd.cmd = [0]* (ICE_AIR_CHANNEL + 1)
            self.node.air_cmd.command_value = 0
            return

        if self.rp_state == RPFlags.STARTING:
            self.node.cmd.cmd[ICE_THR_CHANNEL] = 3500
            self.node.air_cmd.command_value = 2000
            return

        if self.mode == ICERunnerMode.SIMPLE:
            self.node.cmd.cmd[ICE_THR_CHANNEL] = self.configuration.rpm
            # self.dronecan_commander.cmd.cmd[ICE_AIR_CHANNEL] = MAX_AIR_OPEN
        elif self.mode == ICERunnerMode.PID:
            self.node.cmd.cmd[ICE_THR_CHANNEL] = int(self.pid_controller.get_pid_command(self.node.state.rpm))
            # self.dronecan_commander.cmd.cmd[ICE_AIR_CHANNEL] = MAX_AIR_OPEN
        elif self.mode == ICERunnerMode.RPM:
            self.node.cmd.cmd[ICE_THR_CHANNEL] = self.configuration.rpm
            # self.dronecan_commander.cmd.cmd[ICE_AIR_CHANNEL] = MAX_AIR_OPEN

    def stop(self) -> None:
        self.rp_state = RPFlags.STOPPING
        RaspberryMqttClient.to_stop = 0
        self.send_log()
        self.start_time = 0

    def set_state(self, cond_exceeded: bool) -> None:

        ice_state = self.node.state.ice_state
        rpm = self.node.state.rpm
        rp_state = self.rp_state

        if cond_exceeded:
            logging.info(f"STOP\t-\tconditions exceeded")
            self.stop()
            RaspberryMqttClient.publish_stop_reason("Conditions exceeded")
            return

        if rp_state > RPFlags.STARTING or ice_state == RecipFlags["FAULT"]:
            self.start_time = 0
            logger.debug(f"STATE\t-\t stopped, rp state {rp_state.name}, ice state {ice_state.name}")
            return

        if rp_state == RPFlags.STARTING:
            if time.time() - self.start_time > 30:
                self.rp_state = RPFlags.STOPPING
                logger.error("STARTING\t-\tstart time exceeded")
                self.send_log()
                return
            if ice_state == RecipFlags.RUNNING and rpm > 1500 and time.time_ns() - self.prev_waiting_state_time > 3*10**9:
                logger.info("STARTING\t-\tstarted successfully")
                self.rp_state = RPFlags.RUNNING
                return

        if ice_state == RecipFlags.WAITING:
            self.prev_waiting_state_time = time.time_ns()
            self.rp_state = RPFlags.STARTING
            logger.info("WAITING\t-\twaiting state")

    async def spin(self) -> None:
        self.report_status()
        self.report_state()
        self.rp_state_start = self.rp_state
        ice_state = self.node.state.ice_state
        if ice_state == RecipFlags.NOT_CONNECTED:
            logger.warning("NOT_CONNECTED\t-\tNo ICE connected")
            self.rp_state = RPFlags.NOT_CONNECTED
            self.node.cmd.cmd = [0] * (ICE_THR_CHANNEL + 1)
            self.report_status()
            self.node.spin()
            await asyncio.sleep(1)
            return

        if ice_state == RecipFlags.STOPPED:
            if self.rp_state != RPFlags.STARTING:
                self.rp_state = RPFlags.STOPPED
        # self.check_buttons()
        self.check_mqtt_cmd()
        cond_exceeded = self.check_conditions()
        self.set_state(cond_exceeded)
        self.set_command()
        logger.debug(f"CMD\t-\t{list(self.node.cmd.cmd)}")
        self.node.spin()
        await asyncio.sleep(0.05)

    def report_state(self) -> None:
        if time.time() - self.prev_state_report_time > 0.5:
            RaspberryMqttClient.publish_state(self.rp_state.value)

    def report_status(self) -> None:
        if self.prev_report_time + self.reporting_period < time.time():
            state_dict = self.node.state.to_dict()
            if self.start_time > 0:
                state_dict["start_time"] = datetime.datetime.fromtimestamp(self.start_time).strftime('%Y-%m-%d %H:%M:%S')
            else:
                state_dict["start_time"] = "not started"
            RaspberryMqttClient.publish_status(state_dict)
            RaspberryMqttClient.publish_messages(self.node.messages)
            self.prev_report_time = time.time()

    def check_buttons(self):
        """The function checks the state of the stop button"""
        # TODO: make button to be nessesary to set the state from MQTT
        stop_switch = GPIO.input(start_stop_pin)
        if self.last_button_cmd == stop_switch:
            return
        if stop_switch:
            if self.rp_state == RPFlags.STARTING or self.rp_state == RPFlags.RUNNING:
                self.rp_state = RPFlags.STOPPING
            logger.info(f"BUTTON\t  Button released, state: {self.rp_state}")
        else:
            if self.rp_state > RPFlags.STARTING:
                self.rp_state = RPFlags.STARTING
                self.start_time = time.time()
            logger.info(f"BUTTON\t  Button pressed, state: {self.rp_state}")
        self.last_button_cmd = stop_switch

    def check_mqtt_cmd(self):
        if RaspberryMqttClient.to_stop:
            self.rp_state = RPFlags.STOPPING
            RaspberryMqttClient.to_stop = 0
            self.send_log()
            logger.info(f"MQTT\t-\tCOMMAND\t stop, state: {self.rp_state}")
        if RaspberryMqttClient.to_run:
            if self.rp_state > RPFlags.STARTING:
                self.rp_state = RPFlags.STARTING
                self.start_time = time.time()
            logger.info(f"MQTT\t-\tCOMMAND\t run, state: {self.rp_state}")
            RaspberryMqttClient.to_run = 0

    def send_log(self) -> None:
        CanNode.save_file()
        RaspberryMqttClient.rp_logs["candump"] = CanNode.candump_filename
        RaspberryMqttClient.rp_logs["output"] = CanNode.output_filename
        RaspberryMqttClient.publish_log()
        CanNode.change_file()
        logger.info(f"SEND\t-\tlog {CanNode.output_filename}")

    async def run(self) -> None:
        self.send_log()
        while True:
            try:
                await self.spin()
            except Exception as e:
                logger.error(f"{e}\n{traceback.format_exc()}")
                continue

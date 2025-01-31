#!/usr/bin/env python3
# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import asyncio
import datetime
from enum import IntEnum
import time
import traceback
from node import CanNode, start_dronecan_handlers, MAX_AIR_OPEN, ICE_THR_CHANNEL, ICE_AIR_CHANNEL
from common.ICEState import ICEState, RecipState
from common.RPStates import RPState
from common.IceRunnerConfiguration import IceRunnerConfiguration
from mqtt_client import RaspberryMqttClient
import logging

# # GPIO setup
# import RPi.GPIO as GPIO # Import Raspberry Pi GPIO library
# GPIO.setwarnings(True) # Ignore warning for now
# GPIO.setmode(GPIO.BCM) # Use physical pin numbering
# start_stop_pin = 24
# # Setup CAN terminator
# resistor_pin = 23
# GPIO.setup(resistor_pin, GPIO.OUT)
# GPIO.output(resistor_pin, GPIO.HIGH)

# GPIO.setup(start_stop_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # Start/Stop button

class ICEFlags:
    def __init__(self) -> None:
        self.throttle_ex: bool = False
        self.temp_ex: bool = False
        self.rpm_ex: bool = False
        self.vin_ex: bool = False
        self.vibration_ex: bool = False
        self.time_ex: bool = False
        self.rpm_min_ex: bool = False

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
        self.rp_state: RPState = RPState.NOT_CONNECTED
        self.reporting_period: float = reporting_period
        self.node: CanNode = CanNode()
        self.node.connect()
        self.configuration: IceRunnerConfiguration = configuration
        self.flags: ICEFlags = ICEFlags()
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
        if state.ice_state == RecipState["NOT_CONNECTED"]:
            self.rp_state = RPState.NOT_CONNECTED
            logging.getLogger(__name__).warning("STATUS:\tice not connected")
            return 0
        if time.time() - CanNode.last_message_receive_time > 1:
            logging.critical("STATUS:\tToo long time without messages")
            CanNode.state = ICEState()
        if self.start_time <= 0 or state.ice_state > RPState.STARTING:
            self.flags.vin_ex = self.configuration.min_vin_voltage > state.voltage_in
            self.flags.temp_ex = self.configuration.max_temperature < state.temp
            eng_time_ex = False
            if state.engaged_time is not None:
              eng_time_ex = state.engaged_time > 40 * 60 * 60
              if eng_time_ex:
                  logging.getLogger(__name__).warning(f"STATUS:\tEngaged time {state.engaged_time} is exeeded")
            if self.flags.vin_ex or self.flags.temp_ex or eng_time_ex:
                logging.getLogger(__name__).warning(f"STATUS:\tFlags exceeded: vin {self.flags.vin_ex} temp {self.flags.temp_ex} engaged time {eng_time_ex}")
            return sum([self.flags.vin_ex, self.flags.temp_ex,eng_time_ex])
        if self.rp_state == RPState.RUNNING:
            self.flags.rpm_min_ex = 100 > state.rpm
        else:
            self.flags.rpm_min_ex = False
        if self.configuration.min_fuel_volume < 100:
            self.fuel_level_ex = self.configuration.min_fuel_volume > state.fuel_level_percent
        else:
            self.fuel_level_ex = self.configuration.min_fuel_volume > state.fuel_level

        self.flags.throttle_ex = self.configuration.max_gas_throttle < state.throttle
        self.flags.temp_ex = self.configuration.max_temperature < state.temp
        self.flags.rpm_ex = self.configuration.rpm  + 1000 < state.rpm
        self.flags.time_ex = self.start_time > 0 and self.configuration.time < time.time() - self.start_time
        self.flags.vibration_ex = self.node.has_imu and self.configuration.max_vibration < state.vibration
        flags_attr = vars(self.flags)
        if self.flags.vibration_ex or self.flags.time_ex or self.flags.rpm_ex or self.flags.throttle_ex or self.flags.temp_ex or self.fuel_level_ex or self.flags.rpm_min_ex:
            logging.getLogger(__name__).warning(f"STATUS:\tFlags exceeded: vibration {self.flags.vibration_ex} time {self.flags.time_ex} rpm {self.flags.rpm_ex}: {self.configuration.rpm, state.rpm} throttle {self.flags.throttle_ex} temp {self.flags.temp_ex} fuel level {self.fuel_level_ex} rpm min {self.flags.rpm_min_ex}")
        return sum([flags_attr[name] for name in flags_attr.keys() if flags_attr[name]])

    def set_command(self) -> None:
        if self.rp_state == RPState.NOT_CONNECTED or self.rp_state > RPState.STARTING:
            self.node.cmd.cmd = [0]* (ICE_AIR_CHANNEL + 1)
            self.node.air_cmd.command_value = 0
            return

        if self.rp_state == RPState.STARTING:
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

    def set_state(self, cond_exceeded: bool) -> None:

        ice_state = self.node.state.ice_state
        rpm = self.node.state.rpm
        rp_state = self.rp_state

        if cond_exceeded or rp_state > RPState.STARTING or ice_state == RecipState["FAULT"]:
            self.start_time = 0
            logging.getLogger(__name__).info(f"STOP:\tconditions exceeded {bool(cond_exceeded)}, rp state {rp_state}, ice state {ice_state}")
            if self.rp_state < RPState.STOPPED:
                self.rp_state = RPState.STOPPING
                self.send_log()
                return

        if rp_state == RPState.STARTING:
            if time.time() - self.start_time > 30:
                self.rp_state = RPState.STOPPING
                logging.getLogger(__name__).error("STARTING:\tstart time exceeded")
                self.send_log()
                return
            if ice_state == RecipState.RUNNING and rpm > 1500 and time.time_ns() - self.prev_waiting_state_time > 3*10**9:
                logging.getLogger(__name__).info("STARTING:\tstarted successfully")
                self.rp_state = RPState.RUNNING
                return
        if ice_state == RecipState.WAITING:
            self.prev_waiting_state_time = time.time_ns()
            self.rp_state = RPState.STARTING
            logging.getLogger(__name__).info("WAITING:\twaiting state")

    async def spin(self) -> None:
        self.report_status()
        self.report_state()
        self.rp_state_start = self.rp_state
        ice_state = self.node.state.ice_state
        if ice_state == RecipState.NOT_CONNECTED:
            logging.getLogger(__name__).error("NOT_CONNECTED:\tNo ICE connected")
            self.rp_state = RPState.NOT_CONNECTED
            self.node.cmd.cmd = [0] * (ICE_THR_CHANNEL + 1)
            self.node.spin()
            self.report_status()
            await asyncio.sleep(1)
            return

        if ice_state == RecipState.STOPPED:
            if self.rp_state != RPState.STARTING:
                self.rp_state = RPState.STOPPED
        # self.check_buttons()
        self.check_mqtt_cmd()
        cond_exceeded = self.check_conditions()
        self.set_state(cond_exceeded)
        self.set_command()
        logging.getLogger(__name__).info(f"CMD:\t{list(self.node.cmd.cmd)}")
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
            state_dict["state"] = self.rp_state.name
            RaspberryMqttClient.publish_status(state_dict)
            RaspberryMqttClient.publish_messages(self.node.messages)
            self.prev_report_time = time.time()
            logging.getLogger(__name__).info(f"SEND:\tstate {self.rp_state.name}")

    def check_buttons(self):
        """The function checks the state of the stop button"""
        # TODO: make button to be nessesary to set the state from MQTT
        stop_switch = GPIO.input(start_stop_pin)
        if self.last_button_cmd == stop_switch:
            return
        if stop_switch:
            if self.rp_state == RPState.STARTING or self.rp_state == RPState.RUNNING:
                self.rp_state = RPState.STOPPING
            logging.getLogger(__name__).info(f"BUTTON\t|  Button released, state: {self.rp_state}")
        else:
            if self.rp_state > RPState.STARTING:
                self.rp_state = RPState.STARTING
                self.start_time = time.time()
            logging.getLogger(__name__).info(f"BUTTON\t|  Button pressed, state: {self.rp_state}")
        self.last_button_cmd = stop_switch

    def check_mqtt_cmd(self):
        if RaspberryMqttClient.to_stop:
            self.rp_state = RPState.STOPPING
            RaspberryMqttClient.to_stop = 0
            self.send_log()
            logging.getLogger(__name__).info(f"MQTT:\tCOMMAND\t| stop, state: {self.rp_state}")
        if RaspberryMqttClient.to_run:
            if self.rp_state > RPState.STARTING:
                self.rp_state = RPState.STARTING
                self.start_time = time.time()
            logging.getLogger(__name__).info(f"MQTT:\tCOMMAND\t| run, state: {self.rp_state}")
            RaspberryMqttClient.to_run = 0

    def send_log(self) -> None:
        CanNode.save_file()
        RaspberryMqttClient.rp_logs["candump"] = CanNode.candump_filename
        RaspberryMqttClient.rp_logs["output"] = CanNode.output_filename
        RaspberryMqttClient.publish_log()
        CanNode.change_file()
        logging.getLogger(__name__).info(f"SEND:\tlog {CanNode.output_filename}")

    async def run(self) -> None:
        self.send_log()
        while True:
            try:
                await self.spin()
            except Exception as e:
                logging.getLogger(__name__).error(f"{e}\n{traceback.format_exc()}")
                continue

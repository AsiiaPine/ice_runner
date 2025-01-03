#!/usr/bin/env python3
# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import asyncio
import datetime
from enum import IntEnum
from io import TextIOWrapper
import os
import time
import traceback
from typing import Any, Dict
import dronecan
from common.ICEState import ICEState, RecipStateDict
from common.RPStates import RPStatesDict, get_rp_state_name
from common.IceRunnerConfiguration import IceRunnerConfiguration
from mqtt_client import RaspberryMqttClient
from raccoonlab_tools.dronecan.utils import ParametersInterface
from raccoonlab_tools.dronecan.global_node import DronecanNode
from logging import handlers
import logging
# import logging_configurator
# logger = logging_configurator.AsyncLogger(__name__)

# GPIO setup
# import RPi.GPIO as GPIO # Import Raspberry Pi GPIO library
# GPIO.setwarnings(True) # Ignore warning for now
# GPIO.setmode(GPIO.BCM) # Use physical pin numbering
# # on_off_pin = 25
# start_stop_pin = 24
# # Setup CAN terminator
# resistor_pin = 23
# GPIO.setup(resistor_pin, GPIO.OUT)
# GPIO.output(resistor_pin, GPIO.HIGH)

# # GPIO.setup(on_off_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # On/Off button TODO: check pin
# GPIO.setup(start_stop_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # Start/Stop button

ICE_THR_CHANNEL = 7
ICE_AIR_CHANNEL = 10
MAX_AIR_OPEN = 8191


def safely_write_to_file(temp_filename: str, original_filename: str, last_sync_time: float) -> float:
    try:
        if time.time() - last_sync_time > 1:
            logging.getLogger(__name__).info("CANDUMP\tSaving data")

            # With and open both files safely using 'with' context manager
            with open(temp_filename, "r+") as temp_output_file:
                # Use os.open for setting O_SYNC flag for synchronous writing
                fd = os.open(original_filename, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_SYNC)
                with open(fd, "a") as output:
                    lines = temp_output_file.readlines()
                    output.writelines(lines)
                    output.flush()
                    os.fsync(output.fileno())
                    output.close()
                # safely truncate the temporary file after successful copying
                temp_output_file.truncate(0)

            last_sync_time = time.time()
        return last_sync_time

    except Exception as e:
        print(f"An error occurred: {e}")
        logging.getLogger(__name__).error(f"An error occurred: {e}")
        return last_sync_time

class DronecanCommander:
    node = None

    @classmethod
    def connect(cls) -> None:
        node: DronecanNode = DronecanNode()
        cls.node = node
        cls.messages: Dict[str, Any] = {}
        cls.state: ICEState = ICEState()
        cls.air_cmd = dronecan.uavcan.equipment.actuator.Command(actuator_id=ICE_AIR_CHANNEL, command_value=0)
        cls.cmd = dronecan.uavcan.equipment.esc.RawCommand(cmd=[0]*(ICE_AIR_CHANNEL + 1))
        cls.node.sub_once(dronecan.uavcan.equipment.ice.reciprocating.Status)
        cls.node.sub_once(dronecan.uavcan.equipment.ahrs.RawIMU)
        cls.prev_broadcast_time = 0
        cls.param_interface = ParametersInterface(node.node, target_node_id=node.node.node_id)
        cls.has_imu = False
        cls.output_filename = f"logs/raspberry/messages_{datetime.datetime.now().strftime('%Y_%m-%d_%H_%M_%S')}.log"
        cls.temp_output_filename = f"logs/raspberry/temp_messages_{datetime.datetime.now().strftime('%Y_%m-%d_%H_%M_%S')}.log"
        cls.temp_output_file: TextIOWrapper = open(cls.temp_output_filename, "a")
        cls.last_sync_time = 0
        print("all messages will be in ", cls.output_filename)

    @classmethod
    def spin(cls) -> None:
        cls.node.node.spin(0.05)
        if time.time() - cls.prev_broadcast_time > 0.1:
            cls.prev_broadcast_time = time.time()
            cls.node.publish(cls.cmd)
            cls.node.publish(dronecan.uavcan.equipment.actuator.ArrayCommand(commands = [cls.air_cmd]))

def dump_msg(msg: dronecan.node.TransferEvent) -> None:
    DronecanCommander.temp_output_file.write(dronecan.to_yaml(msg) + "\n")
    DronecanCommander.last_sync_time = safely_write_to_file(DronecanCommander.temp_output_filename, DronecanCommander.output_filename, DronecanCommander.last_sync_time)

def fuel_tank_status_handler(msg: dronecan.node.TransferEvent) -> None:
    DronecanCommander.messages['dronecan.uavcan.equipment.ice.FuelTankStatus'] = dronecan.to_yaml(msg.message)
    DronecanCommander.state.update_with_fuel_tank_status(msg)
    dump_msg(msg)
    logging.debug(f"MES:\tReceived fuel tank status")

def raw_imu_handler(msg: dronecan.node.TransferEvent) -> None:
    DronecanCommander.state.update_with_raw_imu(msg)
    DronecanCommander.messages['uavcan.equipment.ahrs.RawIMU'] = dronecan.to_yaml(msg.message)
    DronecanCommander.has_imu = True
    if DronecanCommander.state.engaged_time is None:
        DronecanCommander.param_interface._target_node_id = msg.message.source_node_id
        param = DronecanCommander.param_interface.get("status.engaged_time")
        DronecanCommander.state.engaged_time = param.value
    dump_msg(msg)
    logging.debug(f"MES:\tReceived raw imu")

def node_status_handler(msg: dronecan.node.TransferEvent) -> None:
    if msg.transfer.source_node_id == DronecanCommander.node.node_id:
        return
    DronecanCommander.state.update_with_node_status(msg)
    DronecanCommander.messages['uavcan.protocol.NodeStatus'] = dronecan.to_yaml(msg.message)
    dump_msg(msg)
    logging.debug(f"MES:\tReceived node status")

def ice_reciprocating_status_handler(msg: dronecan.node.TransferEvent) -> None:
    DronecanCommander.state.update_with_resiprocating_status(msg)
    DronecanCommander.messages['uavcan.equipment.ice.reciprocating.Status'] = dronecan.to_yaml(msg.message)
    dump_msg(msg)
    logging.debug(f"MES:\tReceived ICE reciprocating status")

def start_dronecan_handlers() -> None:
    DronecanCommander.node.node.add_handler(dronecan.uavcan.equipment.ice.reciprocating.Status, ice_reciprocating_status_handler)
    DronecanCommander.node.node.add_handler(dronecan.uavcan.equipment.ahrs.RawIMU, raw_imu_handler)
    DronecanCommander.node.node.add_handler(dronecan.uavcan.protocol.NodeStatus, node_status_handler)
    DronecanCommander.node.node.add_handler(dronecan.uavcan.equipment.ice.FuelTankStatus, fuel_tank_status_handler)

class ICEFlags:
    def __init__(self) -> None:
        self.throttle_ex = False
        self.temp_ex = False
        self.rpm_ex = False
        self.vin_ex = False
        self.vibration_ex = False
        self.time_ex = False
        self.rpm_min_ex = False

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
        self.rp_state = RPStatesDict["STOPPED"]
        self.reporting_period = reporting_period
        self.dronecan_commander = DronecanCommander
        self.dronecan_commander.connect()
        start_dronecan_handlers()
        self.configuration = configuration
        self.flags = ICEFlags()
        self.start_time = 0
        self.prev_waiting_state_time = 0
        self.mode = ICERunnerMode(configuration.mode)
        self.prev_report_time = 0
        self.prev_state_report_time = 0
        if self.mode == ICERunnerMode.PID:
            self.pid_controller = PIDController(configuration.rpm)
        self.last_button_cmd = 1


    def check_conditions(self) -> int:
        # check if conditions are exeeded
        state = self.dronecan_commander.state
        if state.ice_state == RecipStateDict["NOT_CONNECTED"]:
            self.rp_state = RPStatesDict["NOT_CONNECTED"]
            logging.getLogger(__name__).warning("STATUS:\tice not connected")
            return 0
        if time.time() - DronecanCommander.last_sync_time > 4:
            logging.critical("STATUS:\tToo long time without messages")
            DronecanCommander.state = ICEState()
        if self.start_time <= 0 or state.ice_state > RPStatesDict["STARTING"]:
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
        if self.rp_state == RPStatesDict["RUNNING"]:
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
        self.flags.vibration_ex = self.dronecan_commander.has_imu and self.configuration.max_vibration < state.vibration
        flags_attr = vars(self.flags)
        if self.flags.vibration_ex or self.flags.time_ex or self.flags.rpm_ex or self.flags.throttle_ex or self.flags.temp_ex or self.fuel_level_ex or self.flags.rpm_min_ex:
            logging.getLogger(__name__).warning(f"STATUS:\tFlags exceeded: vibration {self.flags.vibration_ex} time {self.flags.time_ex} rpm {self.flags.rpm_ex}: {self.configuration.rpm, state.rpm} throttle {self.flags.throttle_ex} temp {self.flags.temp_ex} fuel level {self.fuel_level_ex} rpm min {self.flags.rpm_min_ex}")
        return sum([flags_attr[name] for name in flags_attr.keys() if flags_attr[name]])

    def set_command(self) -> None:
        if self.rp_state == RPStatesDict["NOT_CONNECTED"] or self.rp_state > RPStatesDict["STARTING"]:
            self.dronecan_commander.cmd.cmd = [0]* (ICE_AIR_CHANNEL + 1)
            self.dronecan_commander.air_cmd.command_value = 0
            return

        if self.rp_state == RPStatesDict["STARTING"]:
            self.dronecan_commander.cmd.cmd[ICE_THR_CHANNEL] = 3500
            self.dronecan_commander.air_cmd.command_value = 2000
            return

        if self.mode == ICERunnerMode.SIMPLE:
            self.dronecan_commander.cmd.cmd[ICE_THR_CHANNEL] = self.configuration.rpm
            # self.dronecan_commander.cmd.cmd[ICE_AIR_CHANNEL] = MAX_AIR_OPEN
        elif self.mode == ICERunnerMode.PID:
            self.dronecan_commander.cmd.cmd[ICE_THR_CHANNEL] = int(self.pid_controller.get_pid_command(self.dronecan_commander.state.rpm))
            # self.dronecan_commander.cmd.cmd[ICE_AIR_CHANNEL] = MAX_AIR_OPEN
        elif self.mode == ICERunnerMode.RPM:
            self.dronecan_commander.cmd.cmd[ICE_THR_CHANNEL] = self.configuration.rpm
            # self.dronecan_commander.cmd.cmd[ICE_AIR_CHANNEL] = MAX_AIR_OPEN

    def set_state(self, cond_exceeded: bool) -> None:

        ice_state = self.dronecan_commander.state.ice_state
        rpm = self.dronecan_commander.state.rpm
        rp_state = self.rp_state

        if cond_exceeded or rp_state > RPStatesDict["STARTING"] or ice_state == RecipStateDict["FAULT"]:
            self.start_time = 0
            logging.getLogger(__name__).info(f"STOP:\tconditions exceeded {bool(cond_exceeded)}, rp state {rp_state}, ice state {ice_state}")
            if self.rp_state < RPStatesDict["STOPPED"]:
                self.rp_state = RPStatesDict["STOPPING"]
                return
        if rp_state == RPStatesDict["STARTING"]:
            if time.time() - self.start_time > 30:
                self.rp_state = RPStatesDict["STOPPING"]
                logging.getLogger(__name__).error("STARTING:\tstart time exceeded")
                return
            if ice_state == RecipStateDict["RUNNING"] and rpm > 1500 and time.time_ns() - self.prev_waiting_state_time > 3*10**9:
                logging.getLogger(__name__).info("STARTING:\tstarted successfully")
                self.rp_state = RPStatesDict["RUNNING"]
                return
        if ice_state == RecipStateDict["WAITING"]:
            self.prev_waiting_state_time = time.time_ns()
            self.rp_state = RPStatesDict["STARTING"]
            logging.getLogger(__name__).info("WAITING:\twaiting state")

    async def spin(self) -> None:
        self.report_status()
        self.report_state()
        self.rp_state_start = self.rp_state
        ice_state = self.dronecan_commander.state.ice_state
        if ice_state == RecipStateDict["NOT_CONNECTED"]:
            logging.getLogger(__name__).error("NOT_CONNECTED:\tNo ICE connected")
            self.rp_state = RPStatesDict["NOT_CONNECTED"]
            self.dronecan_commander.cmd.cmd = [0] * (ICE_THR_CHANNEL + 1)
            self.dronecan_commander.spin()
            self.report_status()
            await asyncio.sleep(1)
            return

        if ice_state == RecipStateDict["STOPPED"]:
            if self.rp_state != RPStatesDict["STARTING"]:
                self.rp_state = RPStatesDict["STOPPED"]
        # self.check_buttons()
        self.check_mqtt_cmd()
        cond_exceeded = self.check_conditions()
        self.set_state(cond_exceeded)
        self.set_command()
        logging.getLogger(__name__).info(f"CMD:\t{list(self.dronecan_commander.cmd.cmd)}")
        self.dronecan_commander.spin()
        await asyncio.sleep(0.05)

    def report_state(self) -> None:
        if time.time() - self.prev_state_report_time > 0.5:
            RaspberryMqttClient.get_client().publish("ice_runner/raspberry_pi/{rp_id}/state", get_rp_state_name(self.rp_state))

    def report_status(self) -> None:
        if self.prev_report_time + self.reporting_period < time.time():
            state_dict = self.dronecan_commander.state.to_dict()
            state_dict["start_time"] = self.start_time
            state_dict["state"] = get_rp_state_name(self.rp_state)
            RaspberryMqttClient.publish_status(state_dict)
            RaspberryMqttClient.publish_messages(self.dronecan_commander.messages)
            self.prev_report_time = time.time()
            logging.getLogger(__name__).info(f"SEND:\tstate {get_rp_state_name(self.rp_state)}")

    async def run(self) -> None:
        while True:
            try:
                await self.spin()
            except dronecan.transport.TransferError as e:
                logging.getLogger(__name__).error(f"{e}\n{traceback.format_exc()}")
                continue
            except Exception as e:
                logging.getLogger(__name__).error(f"{e}\n{traceback.format_exc()}")
                continue

    def check_buttons(self):
        """The function checks the state of the stop button"""
        # TODO: make button to be nessesary to set the state from MQTT
        stop_switch = GPIO.input(start_stop_pin)
        if self.last_button_cmd == stop_switch:
            return
        if stop_switch:
            if self.rp_state == RPStatesDict["STARTING"] or self.rp_state == RPStatesDict["RUNNING"]:
                self.rp_state = RPStatesDict["STOPPING"]
            logging.getLogger(__name__).info(f"BUTTON\t|  Button released, state: {self.rp_state}")
        else:
            if self.rp_state > RPStatesDict["STARTING"]:
                self.rp_state = RPStatesDict["STARTING"]
                self.start_time = time.time()
            logging.getLogger(__name__).info(f"BUTTON\t|  Button pressed, state: {self.rp_state}")
        self.last_button_cmd = stop_switch

    def check_mqtt_cmd(self):
        if RaspberryMqttClient.to_stop:
            self.rp_state = RPStatesDict["STOPPING"]
            RaspberryMqttClient.to_stop = 0
            logging.getLogger(__name__).info(f"MQTT:\tCOMMAND\t| stop, state: {self.rp_state}")
        if RaspberryMqttClient.to_run:
            if self.rp_state > RPStatesDict["STARTING"]:
                self.rp_state = RPStatesDict["STARTING"]
                self.start_time = time.time()
            logging.getLogger(__name__).info(f"MQTT:\tCOMMAND\t| run, state: {self.rp_state}")
            RaspberryMqttClient.to_run = 0

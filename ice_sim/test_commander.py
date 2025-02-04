#!/usr/bin/env python3
# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import secrets
import numpy as np
import dronecan
import time
from enum import IntEnum

from raccoonlab_tools.dronecan.global_node import DronecanNode

ICE_CMD_CHANNEL = 7
ICE_AIR_CHANNEL = 10
MAX_RPM = 8500

class ICENodeStatus(IntEnum):
    STOPPED = 0
    RUNNING = 1
    WAITING = 2
    FAULT = 3

class Mode(IntEnum):
    MODE_OPERATIONAL      = 0         # Normal operating mode.
    MODE_INITIALIZATION   = 1         # Initialization is in progress; this mode is entered immediately after startup.
    MODE_MAINTENANCE      = 2         # E.g. calibration, the bootloader is running, etc.
    MODE_SOFTWARE_UPDATE  = 3         # New software/firmware is being loaded.
    MODE_OFFLINE          = 7         # The node is no longer available.

class Health(IntEnum):
    HEALTH_OK         = 0     # The node is functioning properly.
    HEALTH_WARNING    = 1     # A critical parameter went out of range or the node encountered a minor failure.
    HEALTH_ERROR      = 2     # The node encountered a major failure.
    HEALTH_CRITICAL   = 3     # The node suffered a fatal malfunction.

class StarterState(IntEnum):
    STOPPED = 0
    RUNNING = 1
    WAITING = 2
    FINISHED = 3
    FAULT = 4

class Starter:
    def __init__(self, running_period_ms: int, waiting_period_ms: int) -> None:
        self.running_period_ms = running_period_ms
        self.waiting_period_ms = waiting_period_ms
        self.t1_ms = 0
        self.t2_ms = 0
        self.t3_ms = 0
        self.state = StarterState.STOPPED
        self.turn_starter_on = False

    def update(self, is_cmd_engage: bool, is_status_rotating: bool) -> bool:
        crnt_time_ms = time.time_ns() / 1000000
        if not is_cmd_engage:
            self.t1_ms = 0
            self.t2_ms = 0
            self.t3_ms = 0
            self.state = StarterState.STOPPED
        elif crnt_time_ms >= self.t2_ms and crnt_time_ms < self.t3_ms:
            self.turn_starter_on = False
            self.state = StarterState.WAITING
        elif crnt_time_ms >= self.t3_ms and is_status_rotating:
            self.turn_starter_on = False
            self.state = StarterState.FINISHED
        elif crnt_time_ms >= self.t3_ms and not is_status_rotating:
            self.turn_starter_on = True
            self.t1_ms = crnt_time_ms
            self.t2_ms = self.t1_ms + self.running_period_ms
            self.t3_ms = self.t2_ms + self.waiting_period_ms
            self.state = StarterState.RUNNING
        elif crnt_time_ms < self.t2_ms:
            self.turn_starter_on = True
            self.state = StarterState.RUNNING
        else:
            self.turn_starter_on = False
            self.t1_ms = 0
            self.t2_ms = 0
            self.t3_ms = 0
            self.state = StarterState.FAULT
        return self.turn_starter_on

    def get_cycle_time(self) -> int:
        min_cycle_time_ms = 0
        max_cycle_time_ms = self.running_period_ms + self.waiting_period_ms

        cycle_time_ms = max_cycle_time_ms
        if self.t1_ms == 0:
            cycle_time_ms = max_cycle_time_ms
        else:
            cycle_time_ms = max(min_cycle_time_ms, min(time.time_ns() / 1000000 - self.t1_ms, max_cycle_time_ms))
        return cycle_time_ms

class Engine:
    def __init__(self) -> None:
        self.preformance = 4.1 / 8500 # 4.1 HP / 8500 RPM or 3057.37 W / 8500 RPM

        self.rpm = 0
        self.temp = 0
        self.torque = 0
        self.state = ICENodeStatus.STOPPED
        self.starter = Starter(running_period_ms=3000, waiting_period_ms=500)
        self.last_upd = time.time()
        self.ice_acceleration = 0

    def get_power(self) -> float:
        return self.preformance * self.rpm

    def update(self, cmd: int, air_cmd: int) -> None:
        dt = time.time() - self.last_upd
        self.last_upd = time.time()
        if cmd == 0:
            self.state = ICENodeStatus.STOPPED
            self.rpm = 0
            return
        self.ice_acceleration += self.random_d_rpm_change() 
        # ice_acceleration = self.random_d_rpm_change()
        if air_cmd < 100:
            self.ice_acceleration -= air_cmd / 1000
        if air_cmd > 3000:
            self.ice_acceleration += air_cmd / 1000
        if self.rpm < 1500:
            self.random_rpm_change()
        starter_enabled = False
        if self.state == ICENodeStatus.STOPPED:
            starter_enabled = True
        else:
            starter_enabled = self.starter.update(is_cmd_engage=cmd > 0, is_status_rotating=self.rpm > 100)
        if starter_enabled:
            if self.state == ICENodeStatus.STOPPED:
                self.state = ICENodeStatus.RUNNING
        else:
            if self.rpm > 1500:
                self.state = ICENodeStatus.RUNNING
            else:
                self.state = ICENodeStatus.WAITING
                self.rpm = 0
                return
        # print(self.rpm, self.ice_acceleration * dt, cmd, (cmd - self.rpm) * 0.4, self.rpm + self.ice_acceleration * dt + (cmd - self.rpm) * 0.1)
        print(self.rpm, self.ice_acceleration * dt, (cmd - self.rpm) * 0.2)
        self.rpm = int(max(0, self.rpm + self.ice_acceleration * dt + (cmd - self.rpm) * 0.2))

    def random_rpm_change(self) -> float:
        rmp = secrets.randbelow(100)
        self.rpm = max(0, min(self.rpm + rmp, 8500))

    def random_d_rpm_change(self) -> int:
        # d_rpm = secrets.randbelow(100)
        d_rpm = np.sin((time.time() % 100) / (2*3)) * 10
        # return d_rpm * secrets.choice([1, -1])
        return d_rpm

class ICENODE:
    min_command: int = 2000
    status_timeout: float = 0.5
    command: int = 0
    air_cmd: int = 0
    gas_throttle: int = 0
    air_throttle: int = 0

    def __init__(self) -> None:
        self.dt = 0.05
        self.node = DronecanNode(node_id= 11)
        self.rpm = 0
        self.status = ICENodeStatus.STOPPED
        self.temp: float = 0
        self.int_temp: float = 0

        self.current: float = 40

        self.voltage_in: float = 40
        self.voltage_out: float = 5

        self.vibration: float = 0
        self.spark_ignition_time: float = 0
        self.engaged_time: float = 0
        self.mode = Mode.MODE_OPERATIONAL
        self.health = Health.HEALTH_OK
        self.prev_broadcast_time = 0
        self.engine = Engine()

    def create_ice_reciprocating_status(self) -> dronecan.uavcan.equipment.ice.reciprocating.Status:
        return dronecan.uavcan.equipment.ice.reciprocating.Status(
            ecu_index=0,
            state=self.engine.state.value,
            engine_speed_rpm=int(self.engine.rpm),
            atmospheric_pressure_kpa=int(self.engine.rpm),
            engine_load_percent=self.gas_throttle,
            throttle_position_percent=self.air_throttle,
            oil_temperature=self.temp,  
            coolant_temperature=self.int_temp,
            spark_plug_usage=0,
            estimated_consumed_fuel_volume_cm3=self.spark_ignition_time,
            intake_manifold_temperature=self.current,
            intake_manifold_pressure_kpa=5,
            oil_pressure=self.voltage_in)

    def send_ice_reciprocating_status(self, msg: dronecan.uavcan.equipment.ice.reciprocating.Status) -> None:
        self.node.publish(msg)

    def spin(self) -> None:
        self.node.node.spin(0)

        self.engine.update(cmd=self.command, air_cmd=self.air_cmd)
        if time.time() - self.prev_broadcast_time > self.status_timeout:
            self.prev_broadcast_time = time.time()
            self.node.publish(self.create_ice_reciprocating_status())
            self.node.publish(dronecan.uavcan.protocol.NodeStatus(mode=0))
            self.node.publish(dronecan.uavcan.equipment.ice.FuelTankStatus(available_fuel_volume_percent=100))
            self.node.publish(dronecan.uavcan.equipment.ahrs.RawIMU(integration_interval=0))

def get_raw_command(res: dronecan.node.TransferEvent) -> int:
    if res is None:
        return 0
    cmd = res.message.cmd[ICE_CMD_CHANNEL]
    print("ICE\t| ", cmd)
    ICENODE.command = cmd
    ICENODE.gas_throttle = int(max(0, min(cmd, 8191)) / 100)

def get_air_cmd(res: dronecan.node.TransferEvent) -> int:
    if res is None:
        return 0
    for command in res.message.commands:
        if command.actuator_id == ICE_AIR_CHANNEL:
            cmd = command.command_value
            print("AIR\t| ", cmd)
            ICENODE.air_throttle = int(max(1000, min(cmd, 2000)) / 100)
            ICENODE.air_cmd = cmd


if __name__ == "__main__":
    node = ICENODE()
    node.node.node.add_handler(dronecan.uavcan.equipment.esc.RawCommand, get_raw_command)
    node.node.node.add_handler(dronecan.uavcan.equipment.actuator.ArrayCommand, get_air_cmd)
    while True:
        node.spin()

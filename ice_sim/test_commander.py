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

    def get_power(self) -> float:
        return self.preformance * self.rpm

    def update(self, cmd: int, air_cmd: int) -> None:
        dt = time.time() - self.last_upd
        self.last_upd = time.time()
        print("1RPM\t| ", self.rpm)
        print("3CMD\t| ", cmd)
        if cmd == 0:
            self.state = ICENodeStatus.STOPPED
            self.rpm = 0
            return

        ice_acceleration = self.random_d_rpm_change()
        if air_cmd < 100:
            ice_acceleration -= air_cmd % 1000
        if air_cmd > 3000:
            ice_acceleration += air_cmd % 1000
        if self.rpm < 1500:
            print("2RPM\t| ", self.rpm)
            self.random_rpm_change()
            print("3RPM\t| ", self.rpm)
        print("4RPM\t| ", self.rpm)
        starter_enabled = False
        if self.state == ICENodeStatus.STOPPED:
            starter_enabled = True
        else:
            print("STARTER\t| ", starter_enabled)
            starter_enabled = self.starter.update(is_cmd_engage=cmd > 0, is_status_rotating=self.rpm > 100)
        print("STARTER\t| ", starter_enabled)
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
        self.rpm = max(0, min(self.rpm + ice_acceleration * dt + cmd * 0.1, cmd + np.sin(self.rpm / 1000) * (100 + dt)))

    def random_rpm_change(self) -> float:
        rmp = secrets.randbelow(1500)
        self.rpm = max(0, min(self.rpm + rmp, 8500))

    def random_d_rpm_change(self) -> int:
        d_rpm = secrets.randbelow(100)
        return d_rpm * secrets.choice([1, -1])

class ICENODE:
    min_command: int = 2000
    status_timeout: float = 0.5

    def __init__(self) -> None:
        self.dt = 0.05
        self.node = DronecanNode(node_id= 11)
        self.command = dronecan.uavcan.equipment.esc.RawCommand(cmd=[0]*(ICE_CMD_CHANNEL + 1))
        self.rpm = 0
        self.status = ICENodeStatus.STOPPED
        self.temp: float = 0
        self.int_temp: float = 0
        self.gas_throttle: int = 0
        self.air_throttle: int = 0

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
        print("RPM\t| ", self.engine.rpm)
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
            oil_pressure=self.voltage_in,
)

    def send_ice_reciprocating_status(self, msg: dronecan.uavcan.equipment.ice.reciprocating.Status) -> None:
        self.node.publish(msg)

    def get_raw_command(self, timeout_sec=0.03):
        res = self.node.sub_once(
            dronecan.uavcan.equipment.esc.RawCommand, timeout_sec=timeout_sec
        )
        if res is None:
            return 0
        return res.message.cmd[ICE_CMD_CHANNEL]

    def get_air_cmd(self, timeout_sec=0.03):
        res = self.node.sub_once(
            dronecan.uavcan.equipment.actuator.ArrayCommand, timeout_sec=timeout_sec
        )
        if res is None:
            return 0
        for cmd in res.message.commands:
            if cmd.actuator_id == ICE_AIR_CHANNEL:
                return cmd.command_value

    def spin(self) -> None:
        self.node.node.spin(0.05)
        cmd = self.get_raw_command()
        air = self.get_air_cmd()
        self.engine.update(cmd=cmd, air_cmd=air)
        # self.rpm = int(self.rpm + self.random_d_rpm_change() * self.dt + cmd * 0.1)
        if time.time() - self.prev_broadcast_time > self.status_timeout:
            self.prev_broadcast_time = time.time()
            self.node.publish(self.create_ice_reciprocating_status())

if __name__ == "__main__":
    node = ICENODE()
    while True:
        node.spin()
        node.node.node.spin(0.05)


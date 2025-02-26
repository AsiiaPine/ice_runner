#!/usr/bin/env python3
# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

'''The script is used to test the ICE node'''

import time
import secrets
from enum import IntEnum

import argparse
import numpy as np
import dronecan

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
    MODE_INITIALIZATION   = 1         # Initialization is in progress;
                                      # this mode is entered immediately after startup.
    MODE_MAINTENANCE      = 2         # E.g. calibration, the bootloader is running, etc.
    MODE_SOFTWARE_UPDATE  = 3         # New software/firmware is being loaded.
    MODE_OFFLINE          = 7         # The node is no longer available.

class Health(IntEnum):
    HEALTH_OK         = 0     # The node is functioning properly.
    HEALTH_WARNING    = 1     # A critical parameter went out of range or the node encountered
                              # a minor failure.
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
        elif  self.t2_ms <= crnt_time_ms < self.t3_ms:
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
            cycle_time_ms = max(min_cycle_time_ms,
                                min(time.time_ns() / 1000000 - self.t1_ms, max_cycle_time_ms))
        return cycle_time_ms

class Engine:
    def __init__(self) -> None:
        self.rpm = 0
        self.state = ICENodeStatus.STOPPED
        self.starter = Starter(running_period_ms=3000, waiting_period_ms=500)
        self.last_upd = time.time()
        self.ice_acceleration = 0
        self.n_starts = 0
        self.n_starts_max = 3
        self.prev_waiting_time = 0

    def update(self, cmd: int, air_cmd: int) -> None:
        dt = time.time() - self.last_upd
        self.last_upd = time.time()
        if self.state == ICENodeStatus.RUNNING:
            if self.n_starts < self.n_starts_max:
                self.n_starts += 1
                self.rpm = 0
                self.state = ICENodeStatus.WAITING
                self.prev_waiting_time = time.time()
                return
        if self.state == ICENodeStatus.WAITING:
            if time.time() - self.prev_waiting_time > 2:
                self.state = ICENodeStatus.RUNNING
                print("RUNNING")
                return
        if cmd == 0:
            self.state = ICENodeStatus.STOPPED
            self.rpm = 0
            return
        self.ice_acceleration += self.random_d_rpm_change()
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
            starter_enabled = self.starter.update(is_cmd_engage=cmd > 0,
                                                  is_status_rotating=self.rpm > 100)
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
        self.rpm = int(max(0,
                           self.rpm + self.ice_acceleration * dt + (cmd - self.rpm) * 0.2))

    def random_rpm_change(self) -> float:
        rmp = secrets.randbelow(100)
        i = secrets.choice([1, -1])
        self.rpm = max(0, min(self.rpm + i*rmp, 8500))

    def random_d_rpm_change(self) -> int:
        d_rpm = np.sin((time.time() % 100) / (2*3))
        return d_rpm

class ICENODE:
    min_command: int = 2000
    status_timeout: float = 0.5
    command: int = 0
    air_cmd: int = 0
    gas_throttle: int = 0
    air_throttle: int = 0

    @classmethod
    def init(cls) -> None:
        cls.dt = 0.05
        cls.node = DronecanNode(node_id= 11)
        cls.rpm = 0
        cls.current: float = 1
        cls.voltage_in: float = 40
        cls.voltage_out: float = 5

        cls.node.node.mode = Mode.MODE_OPERATIONAL
        cls.node.node.health = Health.HEALTH_OK
        cls.prev_broadcast_time = 0
        cls.engine = Engine()

    @classmethod
    def create_ice_reciprocating_status(cls) -> dronecan.uavcan.equipment.ice.reciprocating.Status:
        return dronecan.uavcan.equipment.ice.reciprocating.Status(
            ecu_index=0,
            state=cls.engine.state.value,
            engine_speed_rpm=int(cls.engine.rpm),
            atmospheric_pressure_kpa=int(cls.engine.rpm),
            engine_load_percent=int(cls.gas_throttle),
            throttle_position_percent=int(cls.air_throttle),
            spark_plug_usage=0,
            estimated_consumed_fuel_volume_cm3=cls.engine.starter.t2_ms,
            intake_manifold_temperature=cls.current,
            intake_manifold_pressure_kpa=5,
            oil_pressure=cls.voltage_in,
            fuel_pressure=cls.voltage_out)

    @classmethod
    def send_ice_reciprocating_status(cls,
                                      msg: dronecan.uavcan.equipment.ice.reciprocating.Status
                                      ) -> None:
        cls.node.publish(msg)

    @classmethod
    def spin(cls) -> None:
        cls.node.node.spin(0)

        cls.engine.update(cmd=cls.command, air_cmd=cls.air_cmd)
        if time.time() - cls.prev_broadcast_time > cls.status_timeout:
            cls.prev_broadcast_time = time.time()
            cls.node.publish(cls.create_ice_reciprocating_status())
            cls.node.publish(
                    dronecan.uavcan.equipment.ice.FuelTankStatus(available_fuel_volume_percent=100))
            cls.node.publish(dronecan.uavcan.equipment.ahrs.RawIMU(integration_interval=0))

def get_raw_command(res: dronecan.node.TransferEvent) -> None:
    if res is None:
        return
    cmd = res.message.cmd[ICE_CMD_CHANNEL]
    print("ICE\t| ", cmd)
    ICENODE.command = cmd
    ICENODE.gas_throttle = int(max(0, min(cmd, 8191)) / 8191 * 100)

def get_air_cmd(res: dronecan.node.TransferEvent) -> None:
    if res is None:
        return
    for command in res.message.commands:
        if command.actuator_id == ICE_AIR_CHANNEL:
            cmd = command.command_value
            print("AIR\t| ", cmd)
            ICENODE.air_throttle = (cmd + 1) * 50 # make it 0-100%
            ICENODE.air_cmd = cmd

def start(args: list['str'] = None) -> None:
    parser = argparse.ArgumentParser()
    # Should just trip on non-empty arg and do nothing otherwise
    parser.parse_args(args)

    ICENODE.init()
    ICENODE.node.node.add_handler(dronecan.uavcan.equipment.esc.RawCommand, get_raw_command)
    ICENODE.node.node.add_handler(dronecan.uavcan.equipment.actuator.ArrayCommand, get_air_cmd)
    while True:
        ICENODE.spin()

if __name__ == "__main__":
    start()

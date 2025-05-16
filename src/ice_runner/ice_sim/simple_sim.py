#!/usr/bin/env python3
# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

'''The script is used to simulate the ICE node'''

import argparse
import os
import pathlib
import sys
import time
import dronecan
from raccoonlab_tools.dronecan.global_node import DronecanNode
from raspberry.can_control.node import ICE_AIR_CHANNEL
from raspberry.can_control.EngineState import Health, Mode, EngineState

class Engine:
    def __init__(self, max_n_tries: int = 3):
        self.state = EngineState.STOPPED
        self.rpm = 0
        self.n_tries = 0
        self.prev_time = 0 
        self.max_n_tries = max_n_tries

    def update(self, cmd: int, air_cmd: int) -> None:
        del air_cmd
        if cmd <= 0:
            self.state = EngineState.STOPPED
            self.rpm = 0
            self.n_tries = 0
            self.prev_time = 0
            return

        if self.n_tries > self.max_n_tries:
            self.rpm = cmd
            self.state = EngineState.STARTER_WAITING
            return

        if time.time() - self.prev_time > 5:
            if self.rpm > 0:
                self.prev_time = time.time()
                self.state = EngineState.STARTER_WAITING
                self.rpm = 0
                print("WAITING")
                return

            self.state = EngineState.STARTER_RUNNING
            self.rpm = 3000
            self.n_tries += 1
            self.prev_time = time.time()
            print("RUNNING")

class ICENODE:
    min_command: int = 2000
    status_timeout: float = 0.5
    command: int = 0
    air_cmd: int = 0
    gas_throttle: int = 0
    air_throttle: int = 0

    def __init__(self, max_n_tries: int = 3) -> None:
        self.node = DronecanNode(node_id= 101)
        self.dt = 0.05
        self.rpm = 0
        self.status = EngineState.STOPPED
        self.temp: float = 0
        self.int_temp: float = 0

        self.current: float = 40

        self.voltage_in: float = 40
        self.voltage_out: float = 5

        self.vibration: float = 0
        self.spark_ignition_time: float = 0
        self.engaged_time: float = 0
        self.node.node.mode = Mode.MODE_OPERATIONAL
        self.node.node.health = Health.HEALTH_OK
        self.prev_broadcast_time = 0
        self.engine = Engine(max_n_tries=max_n_tries)

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

    def send_ice_reciprocating_status(self,
                                      msg: dronecan.uavcan.equipment.ice.reciprocating.Status
                                      ) -> None:
        self.node.publish(msg)

    def spin(self) -> None:
        self.node.node.spin(0)

        self.engine.update(cmd=self.command, air_cmd=self.air_cmd)
        if time.time() - self.prev_broadcast_time > self.status_timeout:
            self.prev_broadcast_time = time.time()
            self.node.publish(self.create_ice_reciprocating_status())
            self.node.publish(
                dronecan.uavcan.equipment.ice.FuelTankStatus(available_fuel_volume_percent=100))
            self.node.publish(dronecan.uavcan.equipment.ahrs.RawIMU(integration_interval=0))

def get_raw_command(res: dronecan.node.TransferEvent) -> None:
    if len(res.message.cmd) < 7:
        return
    cmd = res.message.cmd[7]
    ICENODE.command = cmd
    ICENODE.gas_throttle = int(max(0, min(cmd, 6000)) / 100)

def get_air_cmd(res: dronecan.node.TransferEvent) -> None:
    if res is None:
        return
    for command in res.message.commands:
        if command.actuator_id == ICE_AIR_CHANNEL:
            cmd = command.command_value
            ICENODE.air_throttle = int(max(1000, min(cmd, 2000)) / 100)
            ICENODE.air_cmd = cmd

def start(args: list['str'] = None) -> None:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description='Simple ice simulator. It emulates ice node.')
    parser.add_argument("--n_tries",
                        default=3,
                        type=int,
                        help="number of tries to start the engine")

    parser.add_argument("--log_dir",
                        default=None,
                        type=str,
                        help="Path to log directory")

    parser.add_argument("--vcan",
                        default=None,
                        type=str,
                        help="If vcan creatino is needed, pass the vcan interface name")
    args: argparse.Namespace = parser.parse_args(args)

    if args.vcan is not None:
        filepath = pathlib.Path(__file__).resolve().parent.parent.parent.parent
        dirname = os.path.join(filepath, "scripts").replace(os.getcwd(), "")
        res = os.system(f"sudo .{dirname}/create_vcan.sh {args.vcan}")
        if res != 0:
            print(f"VCAN\t-\tError creating vcan interface {args.vcan}")
            sys.exit(1)
        print(f"VCAN\t-\tInterface {args.vcan} created")

    node = ICENODE(max_n_tries=args.n_tries)
    node.node.node.add_handler(dronecan.uavcan.equipment.esc.RawCommand, get_raw_command)
    node.node.node.add_handler(dronecan.uavcan.equipment.actuator.ArrayCommand, get_air_cmd)
    while True:
        node.spin()

if __name__ == "__main__":
    start()

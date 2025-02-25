# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>
"""The module is used to control the DroneCAN ICE node by raccoonlab"""

import asyncio
import datetime
import logging
import os
import subprocess
import time
from typing import Any, TextIO, Dict
import dronecan
from dronecan.node import Node
from raccoonlab_tools.dronecan.utils import ParametersInterface
from raccoonlab_tools.dronecan.global_node import DronecanNode
from raccoonlab_tools.ice_runner.common.device_manager import DeviceManager
import yaml

from ice_runner.common.ICEState import Health, ICEState, Mode

logger = logging.getLogger(__name__)

ICE_THR_CHANNEL = 7
ICE_AIR_CHANNEL = 10
MAX_AIR_OPEN = 8191

def safely_write_to_file(filename: str) -> float:
    """The function writes to file and syncs it with disk"""
    logger.debug("LOGGER\t Saving data to %s", filename)
    with open(filename, "a") as output:
        output.flush()
        os.fsync(output.fileno())
        output.close()

class CanNode:
    """The class is used to connect to dronecan node and send/receive messages"""
    node = None

    @classmethod
    def connect(cls) -> None:
        """The function establishes dronecan node and starts candump"""
        cls.state: ICEState = ICEState()
        cls.node: Node = DronecanNode(node_id=100).node
        cls.transport = DeviceManager.get_device_port()
        cls.air_cmd = dronecan.uavcan.equipment.actuator.Command(
                                            actuator_id=ICE_AIR_CHANNEL, command_value=0)
        cls.cmd = dronecan.uavcan.equipment.esc.RawCommand(cmd=[0]*(ICE_AIR_CHANNEL + 1))
        cls.prev_broadcast_time: float = 0
        cls.candump_task: asyncio.Task = None
        cls.node.health = Health.HEALTH_OK
        cls.node.mode = Mode.MODE_OPERATIONAL
        cls.change_file()
        cls.last_sync_time = 0
        cls.last_message_receive_time = 0

        cls.messages: Dict[str, Any] = {}
        cls.has_imu = False

    @classmethod
    def spin(cls) -> None:
        """The function spins dronecan node and broadcasts commands"""
        cls.node.spin(timeout=0)
        if time.time() - cls.prev_broadcast_time > 0.1:
            cls.prev_broadcast_time = time.time()
            cls.node.broadcast(cls.cmd)
            cls.node.broadcast(dronecan.uavcan.equipment.actuator.ArrayCommand(
                                                                        commands = [cls.air_cmd]))
            cls.save_file()

    @classmethod
    def save_file(cls) -> None:
        """The function saves candump and humal-readable files"""
        try:
            if time.time() - cls.last_sync_time > 1:
                safely_write_to_file(cls.output_filename)
                safely_write_to_file(cls.candump_filename)
        except Exception as e:
            logger.error("An error occurred: %s",e)

    @classmethod
    def change_file(cls) -> None:
        """The function changes candump and human-readable files, called after stop of a run,
            so the new run will have separated logs"""
        if hasattr(cls, "temp_output_file"):
            os.remove(cls.temp_output_filename)
        crnt_time = datetime.datetime.now().strftime('%Y_%m-%d_%H_%M_%S')
        log_base = os.path.join(cls.log_dir, "logs", "raspberry")
        os.makedirs(log_base, exist_ok=True)
        cls.temp_output_filename = os.path.join(log_base, f"temp_messages_{crnt_time}.log")
        cls.output_filename = os.path.join(log_base, f"messages_{crnt_time}.log")
        cls.temp_output_file: TextIO = open(cls.temp_output_filename, "w+", encoding="utf8")

        cls.__stop_candump__()
        cls.candump_filename = os.path.join(log_base, f"candump_{crnt_time}.log")
        cls.__run_candump__()
        logging.info("SEND\t-\tchanged log files")

    @classmethod
    def __run_candump__(cls) -> None:
        """The function runs candump, used to save dronecan messages"""
        with open(cls.candump_filename, "wb", buffering=0) as cls.candump_file:
            # filter NodeStatus messages
            cls.candump_task = subprocess.Popen(
                                ["candump", "-L", f"{cls.transport},0x15500~0xFFFF00"],
                                stdout=cls.candump_file, bufsize=0)

    @classmethod
    def __stop_candump__(cls) -> None:
        """The function stops candump"""
        if cls.candump_task:
            subprocess.Popen.kill(cls.candump_task)

def dump_msg(msg: dronecan.node.TransferEvent) -> None:
    """The function dumps dronecan message in human-readable format"""
    with open(CanNode.output_filename, "a") as f:
        f.write(dronecan.to_yaml(msg) + "\n")
    # CanNode.temp_output_file.write(dronecan.to_yaml(msg) + "\n")
    CanNode.last_message_receive_time = time.time()

def fuel_tank_status_handler(msg: dronecan.node.TransferEvent) -> None:
    """The function handles dronecan.uavcan.equipment.ice.FuelTankStatus"""
    CanNode.messages['uavcan.equipment.ice.FuelTankStatus'] = yaml.load(
                                                dronecan.to_yaml(msg.message), yaml.BaseLoader)
    CanNode.state.update_with_fuel_tank_status(msg)
    dump_msg(msg)
    logging.debug("MES\t-\tReceived fuel tank status")

def raw_imu_handler(msg: dronecan.node.TransferEvent) -> None:
    """The function handles uavcan.equipment.ahrs.RawIMU"""
    CanNode.state.update_with_raw_imu(msg)
    CanNode.messages['uavcan.equipment.ahrs.RawIMU'] = yaml.load(dronecan.to_yaml(msg.message),
                                                                yaml.BaseLoader)
    CanNode.has_imu = True
    if CanNode.state.engaged_time is None:
        param_interface = ParametersInterface(
                                    CanNode.node.node_id, msg.message.source_node_id)
        param = param_interface.get("status.engaged_time")
        CanNode.state.engaged_time = param.value
    dump_msg(msg)
    logging.debug("MES\t-\tReceived raw imu")

def node_status_handler(msg: dronecan.node.TransferEvent) -> None:
    """The function handles uavcan.protocol.NodeStatus"""
    logging.debug("MES\t-\tReceived node status")
    if msg.transfer.source_node_id == CanNode.node.node_id:
        return
    CanNode.state.update_with_node_status(msg)
    CanNode.messages['uavcan.protocol.NodeStatus'] = yaml.load(dronecan.to_yaml(msg.message),
                                                               yaml.BaseLoader)
    dump_msg(msg)

def ice_reciprocating_status_handler(msg: dronecan.node.TransferEvent) -> None:
    """The function handles uavcan.equipment.ice.reciprocating.Status"""
    CanNode.state.update_with_resiprocating_status(msg)
    CanNode.messages['uavcan.equipment.ice.reciprocating.Status'] = yaml.load(
                                                dronecan.to_yaml(msg.message), yaml.BaseLoader)
    dump_msg(msg)
    logging.debug("MES\t-\tReceived ICE reciprocating status")

def start_dronecan_handlers() -> None:
    """The function starts all handlers for dronecan messages"""
    CanNode.node.add_handler(dronecan.uavcan.equipment.ice.reciprocating.Status,
                             ice_reciprocating_status_handler)
    CanNode.node.add_handler(dronecan.uavcan.equipment.ahrs.RawIMU, raw_imu_handler)
    CanNode.node.add_handler(dronecan.uavcan.protocol.NodeStatus, node_status_handler)
    CanNode.node.add_handler(dronecan.uavcan.equipment.ice.FuelTankStatus, fuel_tank_status_handler)

def stop_dronecan_handlers() -> None:
    """The function stops all handlers for dronecan messages"""
    CanNode.node.remove_handlers(dronecan.uavcan.protocol.NodeStatus)
    CanNode.node.remove_handlers(dronecan.uavcan.equipment.ahrs.RawIMU)
    CanNode.node.remove_handlers(dronecan.uavcan.equipment.ice.reciprocating.Status)
    CanNode.node.remove_handlers(dronecan.uavcan.equipment.ice.FuelTankStatus)

# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>
"""The module is used to control the DroneCAN ICE node by raccoonlab"""

import asyncio
import csv
import datetime
import logging
import os
import subprocess
import time
from typing import Any, List, Dict
import dronecan
from dronecan.node import Node
from raccoonlab_tools.dronecan.utils import ParametersInterface
from raccoonlab_tools.dronecan.global_node import DronecanNode
from raccoonlab_tools.common.device_manager import DeviceManager
import yaml

from raspberry.can_control.EngineState import Health, EngineStatus, Mode

# logger = logging.getLogger(__name__)

ICE_THR_CHANNEL = 7
ICE_AIR_CHANNEL = 10
MAX_AIR_OPEN = 8191

def safely_write_to_file(filename: str) -> float:
    """The function writes to file and syncs it with disk"""
    logging.debug("LOGGER\t Saving data to %s", filename)
    with open(filename, "a") as output:
        output.flush()
        os.fsync(output.fileno())
        output.close()

class CanNode:
    """The class is used to connect to dronecan node and send/receive messages"""
    node: Node|None = None
    log_dir: str = "logs"
    can_output_filenames: Dict[str, str] = {}
    can_output_header_written: Dict[str, bool] = {}
    messages: Dict[str, Any] = {}
    candump_task: asyncio.Task| None = None
    candump_filename: str| None = None
    last_sync_time: float = 0
    last_message_receive_time: float = 0

    @classmethod
    def connect(cls) -> None:
        """The function establishes dronecan node and starts candump"""
        cls.status: EngineStatus = EngineStatus()
        cls.node: Node = DronecanNode(node_id=100).node
        cls.transport = DeviceManager.get_device_port()
        cls.air_cmd = dronecan.uavcan.equipment.actuator.Command(
                                            actuator_id=ICE_AIR_CHANNEL, command_value=0)
        cls.cmd = dronecan.uavcan.equipment.esc.RawCommand(cmd=[0]*(ICE_THR_CHANNEL + 1))
        cls.prev_broadcast_time: float = 0
        cls.node.health = Health.HEALTH_OK
        cls.node.mode = Mode.MODE_OPERATIONAL
        cls.can_output_filenames = {}
        cls.can_output_header_written = {}
        cls.messages: Dict[str, Any] = {}
        cls.can_output_dict_writers: Dict[str, csv.DictWriter] = {}
        cls.change_files()
        cls.has_imu = False

    @classmethod
    def set_log_dir(cls, value: str) -> None:
        cls._log_dir = value

    @classmethod
    def spin(cls) -> None:
        """The function spins dronecan node and broadcasts commands"""
        cls.node.spin(timeout=0)
        if time.time() - cls.prev_broadcast_time > 0.1:
            cls.prev_broadcast_time = time.time()
            cls.node.broadcast(cls.cmd)
            cls.node.broadcast(dronecan.uavcan.equipment.actuator.ArrayCommand(
                                                                        commands = [cls.air_cmd]))
            cls.save_files()

    @classmethod
    def start_dump(cls) -> None:
        """The function restarts dumping"""
        cls.change_files()
        cls.run_candump()

    @classmethod
    def stop_dump(cls) -> None:
        """The function stops dumping"""
        cls.stop_candump()
        cls.save_files()

    @classmethod
    def save_files(cls) -> None:
        """The function saves candump and humal-readable files"""
        try:
            if time.time() - cls.last_sync_time > 5:
                for can_type in cls.can_output_filenames:
                    safely_write_to_file(cls.can_output_filenames[can_type])
                safely_write_to_file(cls.candump_filename)
        except OSError as e:
            if e.errno == 9:  # Bad file descriptor
                logging.error("Bad file descriptor.")
            else:
                logging.error(f"An error occurred: {e}")

    @classmethod
    def change_files(cls) -> None:
        """The function changes candump and human-readable files, called after stop of a run,
            so the new run will have separated logs"""
        crnt_time = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        log_base = os.path.join(cls.log_dir, "raspberry")
        os.makedirs(log_base, exist_ok=True)
        for can_type in cls.can_output_filenames:
            cls.can_output_filenames[can_type] = os.path.join(log_base,
                                                              f"{can_type}_{crnt_time}.csv")
            cls.can_output_header_written = {}

        cls.candump_filename = os.path.join(log_base, f"candump_{crnt_time}.log")
        logging.info("SEND\t-\tchanged log files")

    @classmethod
    def run_candump(cls) -> None:
        """The function runs candump, used to save dronecan messages"""
        assert cls.candump_filename
        with open(cls.candump_filename, "wb", buffering=0) as cls.candump_file:
            # filter NodeStatus messages
            cls.candump_task = subprocess.Popen(
                                ["candump", "-L", f"{cls.transport}"],
                                stdout=cls.candump_file, bufsize=0)

    @classmethod
    def stop_candump(cls) -> None:
        """The function stops candump"""
        if cls.candump_task is not None:
            subprocess.Popen.kill(cls.candump_task)
            cls.candump_task = None

def make_dict_csv_header(d: Dict, prefix: str="") -> List[str]:
    """The function gets csv header"""
    header = []
    if len(prefix) != 0:
        prefix += '_'
    for key, value in d.items():
        if isinstance(value, dict):
            header += make_dict_csv_header(value, prefix+key)
        elif isinstance(value, list) and not isinstance(value, str):
            for i, item in enumerate(value):
                header.append(f"{prefix+key}_{i}")
        else:
            header.append(prefix+key)
    return header

def dict_to_csv_row(d: Dict) -> List[str]:
    """The function gets csv row"""
    row = []
    for key, value in d.items():
        if isinstance(value, dict):
            row += dict_to_csv_row(value)
        elif isinstance(value, list) and not isinstance(value, str):
            for i, item in enumerate(value):
                row.append(f"{item}")
        else:
            row.append(f"{value}")
    return row

def dump_msg(msg: dronecan.node.TransferEvent, can_type: str) -> None:
    """The function dumps dronecan message in human-readable format"""
    CanNode.last_message_receive_time = time.time()
    mes_dict: Dict = yaml.load(dronecan.to_yaml(msg.message), yaml.BaseLoader)
    mes_dict["t"] = time.time()
    with open(CanNode.can_output_filenames[can_type], "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if not can_type in CanNode.can_output_header_written:
            CanNode.can_output_header_written[can_type] = True
            w.writerow(make_dict_csv_header(mes_dict))
        w.writerow(dict_to_csv_row(mes_dict))

def fuel_tank_status_handler(msg: dronecan.node.TransferEvent) -> None:
    """The function handles dronecan.uavcan.equipment.ice.FuelTankStatus"""
    CanNode.messages['uavcan.equipment.ice.FuelTankStatus'] = yaml.load(
                                                dronecan.to_yaml(msg.message), yaml.BaseLoader)
    CanNode.status.update_with_fuel_tank_status(msg)
    dump_msg(msg, "uavcan.equipment.ice.FuelTankStatus")
    logging.debug("MES\t-\tReceived fuel tank status")

def raw_imu_handler(msg: dronecan.node.TransferEvent) -> None:
    """The function handles uavcan.equipment.ahrs.RawIMU"""
    CanNode.status.update_with_raw_imu(msg)
    CanNode.messages['uavcan.equipment.ahrs.RawIMU'] = yaml.load(dronecan.to_yaml(msg.message),
                                                                yaml.BaseLoader)
    CanNode.has_imu = True
    if CanNode.status.engaged_time is None:
        param_interface = ParametersInterface(
                                    CanNode.node.node_id, msg.message.source_node_id)
        param = param_interface.get("status.engaged_time")
        CanNode.status.engaged_time = param.value
    dump_msg(msg, "uavcan.equipment.ahrs.RawIMU")
    logging.debug("MES\t-\tReceived raw imu")

def node_status_handler(msg: dronecan.node.TransferEvent) -> None:
    """The function handles uavcan.protocol.NodeStatus"""
    logging.debug("MES\t-\tReceived node status")
    CanNode.status.update_with_node_status(msg)
    CanNode.messages['uavcan.protocol.NodeStatus'] = yaml.load(dronecan.to_yaml(msg.message),
                                                               yaml.BaseLoader)
    dump_msg(msg, "uavcan.protocol.NodeStatus")

def ice_reciprocating_status_handler(msg: dronecan.node.TransferEvent) -> None:
    """The function handles uavcan.equipment.ice.reciprocating.Status"""
    CanNode.status.update_with_resiprocating_status(msg)
    CanNode.messages['uavcan.equipment.ice.reciprocating.Status'] = yaml.load(
                                                dronecan.to_yaml(msg.message), yaml.BaseLoader)
    dump_msg(msg, "uavcan.equipment.ice.reciprocating.Status")
    logging.debug("MES\t-\tReceived ICE reciprocating status")

def start_dronecan_handlers() -> None:
    """The function starts all handlers for dronecan messages"""
    CanNode.node.add_handler(dronecan.uavcan.equipment.ice.reciprocating.Status,
                             ice_reciprocating_status_handler)
    CanNode.node.add_handler(dronecan.uavcan.equipment.ahrs.RawIMU, raw_imu_handler)
    CanNode.node.add_handler(dronecan.uavcan.protocol.NodeStatus, node_status_handler)
    CanNode.node.add_handler(dronecan.uavcan.equipment.ice.FuelTankStatus, fuel_tank_status_handler)
    CanNode.can_output_filenames["uavcan.equipment.ice.reciprocating.Status"] = None
    CanNode.can_output_filenames["uavcan.equipment.ahrs.RawIMU"] = None
    CanNode.can_output_filenames["uavcan.protocol.NodeStatus"] = None
    CanNode.can_output_filenames["uavcan.equipment.ice.FuelTankStatus"] = None

def stop_dronecan_handlers() -> None:
    """The function stops all handlers for dronecan messages"""
    CanNode.node.remove_handlers(dronecan.uavcan.protocol.NodeStatus)
    CanNode.node.remove_handlers(dronecan.uavcan.equipment.ahrs.RawIMU)
    CanNode.node.remove_handlers(dronecan.uavcan.equipment.ice.reciprocating.Status)
    CanNode.node.remove_handlers(dronecan.uavcan.equipment.ice.FuelTankStatus)



from ast import Dict
import datetime
import logging
import os
import time
from io import TextIOWrapper
from typing import Any
import dronecan
from dronecan.node import Node
from raccoonlab_tools.dronecan.utils import ParametersInterface
from raccoonlab_tools.dronecan.global_node import DronecanNode
from common.ICEState import ICEState

ICE_THR_CHANNEL = 7
ICE_AIR_CHANNEL = 10
MAX_AIR_OPEN = 8191

def safely_write_to_file(temp_filename: str, original_filename: str, last_sync_time: float) -> float:
    try:
        if time.time() - last_sync_time > 1:
            logging.getLogger(__name__).info("LOGGER\tSaving data")

            with open(temp_filename, "r+") as temp_output_file:
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

class CanNode:
    node = None

    @classmethod
    def connect(cls) -> None:
        cls.state: ICEState = ICEState()
        cls.node: Node = DronecanNode().node
        cls.param_interface: ParametersInterface = ParametersInterface(cls.node, target_node_id=cls.node.node_id)

        cls.air_cmd = dronecan.uavcan.equipment.actuator.Command(actuator_id=ICE_AIR_CHANNEL, command_value=0)
        cls.cmd = dronecan.uavcan.equipment.esc.RawCommand(cmd=[0]*(ICE_AIR_CHANNEL + 1))
        cls.prev_broadcast_time: float = 0

        cls.change_file()
        cls.last_sync_time = 0
        print("all messages will be in ", cls.output_filename)

        cls.messages: Dict[str, Any] = {}
        cls.has_imu = False

    @classmethod
    def spin(cls) -> None:
        cls.node.spin(0.05)
        if time.time() - cls.prev_broadcast_time > 0.1:
            cls.prev_broadcast_time = time.time()
            cls.node.broadcast(cls.cmd)
            cls.node.broadcast(dronecan.uavcan.equipment.actuator.ArrayCommand(commands = [cls.air_cmd]))

    @classmethod
    def save_file(cls, filename: str) -> None:
        cls.last_sync_time = safely_write_to_file(cls.temp_output_filename, cls.output_filename, cls.last_sync_time)
        logging.info(f"SEND:\tlog {filename}")

    @classmethod
    def change_file(cls) -> None:
        crnt_time = datetime.datetime.now().strftime('%Y_%m-%d_%H_%M_%S')
        cls.temp_output_filename = f"logs/raspberry/temp_messages_{crnt_time}.log"
        cls.output_filename = f"logs/raspberry/messages_{crnt_time}.log"
        cls.temp_output_file: TextIOWrapper = open(cls.temp_output_filename, "a")
        logging.info(f"SEND:\tchanged log file")

def dump_msg(msg: dronecan.node.TransferEvent) -> None:
    CanNode.temp_output_file.write(dronecan.to_yaml(msg) + "\n")
    CanNode.last_sync_time = safely_write_to_file(CanNode.temp_output_filename, CanNode.output_filename, CanNode.last_sync_time)

def fuel_tank_status_handler(msg: dronecan.node.TransferEvent) -> None:
    CanNode.messages['dronecan.uavcan.equipment.ice.FuelTankStatus'] = dronecan.to_yaml(msg.message)
    CanNode.state.update_with_fuel_tank_status(msg)
    dump_msg(msg)
    logging.debug(f"MES:\tReceived fuel tank status")

def raw_imu_handler(msg: dronecan.node.TransferEvent) -> None:
    CanNode.state.update_with_raw_imu(msg)
    CanNode.messages['uavcan.equipment.ahrs.RawIMU'] = dronecan.to_yaml(msg.message)
    CanNode.has_imu = True
    if CanNode.state.engaged_time is None:
        CanNode.param_interface._target_node_id = msg.message.source_node_id
        param = CanNode.param_interface.get("status.engaged_time")
        CanNode.state.engaged_time = param.value
    dump_msg(msg)
    logging.debug(f"MES:\tReceived raw imu")

def node_status_handler(msg: dronecan.node.TransferEvent) -> None:
    if msg.transfer.source_node_id == CanNode.node.node_id:
        return
    CanNode.state.update_with_node_status(msg)
    CanNode.messages['uavcan.protocol.NodeStatus'] = dronecan.to_yaml(msg.message)
    dump_msg(msg)
    logging.debug(f"MES:\tReceived node status")

def ice_reciprocating_status_handler(msg: dronecan.node.TransferEvent) -> None:
    CanNode.state.update_with_resiprocating_status(msg)
    CanNode.messages['uavcan.equipment.ice.reciprocating.Status'] = dronecan.to_yaml(msg.message)
    dump_msg(msg)
    logging.debug(f"MES:\tReceived ICE reciprocating status")

def start_dronecan_handlers() -> None:
    CanNode.node.add_handler(dronecan.uavcan.equipment.ice.reciprocating.Status, ice_reciprocating_status_handler)
    CanNode.node.add_handler(dronecan.uavcan.equipment.ahrs.RawIMU, raw_imu_handler)
    CanNode.node.add_handler(dronecan.uavcan.protocol.NodeStatus, node_status_handler)
    CanNode.node.add_handler(dronecan.uavcan.equipment.ice.FuelTankStatus, fuel_tank_status_handler)

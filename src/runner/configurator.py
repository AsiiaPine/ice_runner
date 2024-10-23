#!/usr/bin/env python3
# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

from enum import Enum
import time
import dronecan
from raccoonlab_tools.dronecan.utils import Parameter, \
                                            ParametersInterface, \
                                            NodeFinder, \
                                            NodeCommander
import Messages
from typing import List
import dronecan

from raccoonlab_tools.dronecan.global_node import DronecanNode
from raccoonlab_tools.dronecan.utils import (
    Parameter,
    ParametersInterface,
    NodeCommander,
)

PARAM_NODE_ID = "uavcan.node.id"
PARAM_SYSTEM_NAME = "system.name"
MAX_NUM_ICE = 5

class NodeInterface:
    command_type_param_name = ''
    parameters = {}
    
    tx_mes_types = [Messages.NodeStatus]
    rx_mes_types = []

    def __init__(self, destination_node_id: int, node: DronecanNode|None = None) -> None:
        self.node_id = destination_node_id
        self._params_interface = ParametersInterface(node, target_node_id=self.node_id)
        self._commander = NodeCommander(node, target_node_id=self.node_id)

        self._params     : List[Parameter]   = []
        self._int_params : List[Parameter]   = []
        self._str_params : List[Parameter]   = []
        self.__get_parameters__()

    def recv_parameter(self, param: Parameter|int|str) -> Parameter:
        if isinstance(param, Parameter):
            return self._params_interface.get(param.name)
        return self._params_interface.get(param)

    def set_param(self, param: Parameter) -> None:
        """
        """
        self._params_interface.set(param)

    def __get_parameters__(self) -> None:
        params: List[Parameter] = self._params_interface.get_all()
        for param in params:
            if param.name == PARAM_NODE_ID or param.name == PARAM_SYSTEM_NAME:
                continue
            if isinstance(param.value, int):
                self._int_params.append(param)
            elif isinstance(param.value, str):
                self._str_params.append(param)
        self._params = params

    def change_command_type(self, type: int) -> None:
        self.command_type = type
        self._params_interface.set(params=Parameter(name=self.command_type_param_name, value=type))

    @classmethod
    def extend_tx_mes_types(cls, new_types) -> None:
        # Add new types if they're not already present
        for new_type in new_types:
            if new_type not in cls.tx_mes_types:
                cls.tx_mes_types.append(new_type)

class ICENode(NodeInterface):
    nodes_list = []
    unique_param = 'air.cmd'
    command_type_param_name = 'air.cmd'
    tx_mes_types = [Messages.NodeStatus,
                    Messages.ICEReciprocating,
                    Messages.FuelTankStatus]
    rx_mes_types = [Messages.ArrayStatus,
                    Messages.ESCStatus]

    class AirCommandTypes(Enum):
        RAWCOMMAND      = 0,
        ARRAYCOMMAND    = 1

    def __init__(self, destination_node_id: int, node: DronecanNode|None = None):
        ICENode.nodes_list.append(self)
        super().__init__(destination_node_id=destination_node_id, node=node)

    def get_reciprocating_status(self, timeout_sec=0.03):
        res = self.node.sub_once(dronecan.uavcan.equipment.ice.reciprocating, timeout_sec=timeout_sec)
        return Messages.ICEReciprocating.from_message(res.message)

    def get_fuel_tank_status(self, timeout_sec=0.03):
        res = self.node.sub_once(dronecan.uavcan.equipment.ice.FuelTankStatus, timeout_sec=timeout_sec)
        return Messages.FuelTankStatus.from_message(res.message)

class MiniNode(NodeInterface):
    unique_param = "pwm.cmd_type"
    nodes_list = []

    tx_mes_types = [Messages.NodeStatus,
                    Messages.ESCRawCommand]
    rx_mes_types = [Messages.Command,
                    Messages.ArrayCommand]

    class FeedbackTypes(Enum):
        DISABLED    = 0,
        FREQ_1_HZ   = 1,
        FREQ_10_HZ  = 2

    class CommandTypes(Enum):
        RAWCOMMAND  = 0,
        ARRAYCOMMAND = 1,
        HARDPOINT   = 2

    def __init__(self, destination_node_id: int, node: DronecanNode|None = None) -> None:
        MiniNode.nodes_list.append(self)
        super().__init__(destination_node_id=destination_node_id, node=node)
        self.__get_parameters__()
        self.has_imu = True
        for param in self._int_params:
            if param.name == 'imu.mode':
                self.has_imu = True

    def change_pwm_channel(self, channel: int, pwm_num: int) -> None:
        self._params_interface.set(params=Parameter(name=f"pwm{pwm_num}.ch", value=channel))

    def change_feedback_type(self, type: int| FeedbackTypes):
        self._params_interface.set(params=Parameter(name=f"feedback.type", value=type))

    def set_esc_rpm_command(self, command: List[int], timeout_sec=0.03):
        self.node.pub(dronecan.uavcan.equipment.esc.RPMCommand(command=command), timeout_sec=timeout_sec)

    def get_esc_status(self, timeout_sec=0.03):
        res = self.node.sub_once(dronecan.uavcan.equipment.esc.Status, timeout_sec=timeout_sec)
        return Messages.ESCStatus.from_message(res.message)

    def get_esc_rpm_command(self, timeout_sec=0.03):
        res = self.node.sub_once(dronecan.uavcan.equipment.esc.RPMCommand, timeout_sec=timeout_sec)
        return Messages.ESCRPMCommand.from_message(res.message)


def check_node_type(node_id: int) -> NodeInterface:
    DronecanNode()

def main():
    ice_nodes: List[ICENode]    = []
    min_nodes: List[MiniNode]   = []
    node_ids: List[int] = []

    node = DronecanNode()
    nodes_sniffer = NodeFinder(node.node)
    node_ids = nodes_sniffer.find_online_nodes(1.0)

    for node_id in node_ids:
        print(f"Start getting params of {node_id}")
        params_interface = ParametersInterface(target_node_id=node_id)
        params = params_interface.get_all()
        is_mini_node = sum([1 for param in params if param.name == MiniNode.unique_param])
        if is_mini_node:
            min_nodes.append(MiniNode(node_id))
        else:
            ice_nodes.append(ICENode(node_id))
        del params_interface
    print(len(ice_nodes), len(min_nodes))

if __name__ == "__main__":
    main()

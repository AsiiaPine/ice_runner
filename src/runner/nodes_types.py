#!/usr/bin/env python3
# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

from enum import Enum
import logging
import dronecan
from raccoonlab_tools.dronecan.utils import Parameter, \
                                            ParametersInterface, \
                                            NodeCommander
import Messages
from typing import Any, Dict, List
import dronecan

from raccoonlab_tools.dronecan.global_node import DronecanNode
from raccoonlab_tools.dronecan.utils import (
    Parameter,
    ParametersInterface,
    NodeCommander,
)
from logging_configurator import get_logger

PARAM_NODE_ID = "uavcan.node.id"
PARAM_SYSTEM_NAME = "system.name"

class NodeType(Enum):
    ICE = 0,
    MINI = 1,
    UNKNOWN = 2

class NodeInterface:
    """Abstract class for nodes"""
    command_type_param_name = ''

    tx_mes_types = [Messages.NodeStatus]
    rx_mes_types = []

    logger = get_logger(__name__)

    def __init__(self, destination_node_id: int, node: DronecanNode|None = None) -> None:
        self.interface_node = node if node is not None else DronecanNode()
        self.node_id = destination_node_id
        self._params_interface = ParametersInterface(node.node, target_node_id=self.node_id)
        self._commander = NodeCommander(node.node, target_node_id=self.node_id)
        self.parameters: Dict[str, Any] = {}
        self.__get_parameters__()

    def msg_filter(self, transfer: dronecan.node.TransferEvent) -> bool:
        transfer.transfer.source_node_id == self.node_id

    def recv_parameter(self, param: Parameter|int|str) -> Parameter:
        if isinstance(param, Parameter):
            return self._params_interface.get(param.name)
        return self._params_interface.get(param)

    def set_param(self, param: Parameter) -> bool:
        """
        """
        if self._params_interface.set(param):
            return True
        self.logger.error(f"Failed to set parameter {param.name} for node {self.node_id}. Param does not exist")
        return False

    def set_params(self, params: List[Parameter]) -> int:
        """
        Set parameters for node
        :param params: List of parameters
        :return: Number of parameters that were set successfully
        """
        success = 0
        for param in params:
            if not self.set_param(param):
                return success
            success += 1
        return success

    def __get_parameters__(self) -> None:
        params: List[Parameter] = self._params_interface.get_all()
        for param in params:
            self.parameters[param.name] = param.value

    def change_command_type(self, type: int) -> None:
        self.command_type = type
        self._params_interface.set(params=Parameter(name=self.command_type_param_name, value=type))

    @classmethod
    def extend_tx_mes_types(cls, new_types) -> None:
        # Add new types if they're not already present
        for new_type in new_types:
            if new_type not in cls.tx_mes_types:
                cls.tx_mes_types.append(new_type)

    def recieve_message(self, msg_type: str, timeout_sec=0.03) -> Messages.Message|None:
        if msg_type not in self.rx_mes_types:
            NodeInterface.logger.debug(f"Message type {msg_type} is not in {self.node_id} rx_mes_types")
            return None
        res = self.interface_node.sub_once(self.tx_mes_types[msg_type].dronecan_type, timeout_sec=timeout_sec, msg_filter=self.msg_filter)
        if res is None:
            NodeInterface.logger.debug(f"No message {self.tx_mes_types[msg_type].dronecan_type} from node {self.node_id}")
            return None
        return self.tx_mes_types[msg_type].from_message(msg=res.message)

    def send_message(self, msg: Messages.Message, timeout_sec=0.03) -> None:
        if type(msg) not in self.tx_mes_types:
            NodeInterface.logger.debug(f"Message type {type(msg)} is not in {self.node_id} tx_mes_types")
            return
        self.interface_node.pub(msg.dronecan_type(msg), timeout_sec=timeout_sec)

    def get_message_types(self) -> Dict[str, Messages.Message]:

class ICENode(NodeInterface):
    """Class for communication with ICE nodes"""
    unique_param = 'air.cmd'
    command_type_param_name = 'air.cmd'

    tx_mes_types = [Messages.NodeStatus,
                    Messages.ICEReciprocating,
                    Messages.FuelTankStatus]
    rx_mes_types = [Messages.ActuatorStatus,
                    Messages.ESCStatus]

    class AirCommandTypes(Enum):
        RAWCOMMAND      = 0,
        ARRAYCOMMAND    = 1

    def __init__(self, destination_node_id: int, node: DronecanNode|None = None):
        super().__init__(destination_node_id=destination_node_id, node=node)

class MiniNode(NodeInterface):
    """Class for communication with mini nodes"""
    unique_param = "pwm.cmd_type"

    tx_mes_types = [Messages.NodeStatus,
                    Messages.ESCRawCommand]
    rx_mes_types = [Messages.ActuatorCommand,
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
        super().__init__(destination_node_id=destination_node_id, node=node)
        self.__get_parameters__()
        self.has_imu = True
        for param in self.parameters.keys():
            if param == 'imu.mode':
                self.has_imu = True
                self.logger.debug(f"MiniNode {self.node_id} has IMU")
                self.tx_mes_types.append(Messages.RawImu)
                self.tx_mes_types.append(Messages.ImuVibrations)
                return
        self.logger.debug(f"MiniNode {self.node_id} does not have IMU")

    def change_pwm_channel(self, channel: int, pwm_num: int) -> None:
        self._params_interface.set(params=Parameter(name=f"pwm{pwm_num}.ch", value=channel))

    def change_feedback_type(self, type: int| FeedbackTypes):
        self._params_interface.set(params=Parameter(name=f"feedback.type", value=type))

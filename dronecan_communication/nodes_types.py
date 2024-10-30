#!/usr/bin/env python3
# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import enum
import logging
import dronecan
import DronecanMessages as DronecanMessages
from typing import Any, Dict, List
from raccoonlab_tools.dronecan.global_node import DronecanNode
from raccoonlab_tools.dronecan.utils import (
    Parameter,
    ParametersInterface,
    NodeCommander,
)

logger = logging.getLogger(__name__)

PARAM_NODE_ID = "uavcan.node.id"
PARAM_SYSTEM_NAME = "system.name"

class NodeType(enum.IntEnum):
    ICE     = 0,
    MINI    = 1,
    UNKNOWN = 2

class NodeInterface:
    """Abstract class for nodes"""
    name = 'ABS Node'
    command_type_param_name = ''

    rx_mes_types = [DronecanMessages.NodeStatus]
    tx_mes_types = []

    def __init__(self, destination_node_id: int, node: DronecanNode|None = None) -> None:
        self.interface_node = node if node is not None else DronecanNode()
        self.node_id = destination_node_id
        self._params_interface = ParametersInterface(node.node, target_node_id=self.node_id)
        self._commander = NodeCommander(node.node, target_node_id=self.node_id)
        self.parameters: Dict[str, Any] = {}
        self.__get_parameters__()

    def msg_filter(self, transfer: dronecan.node.TransferEvent) -> bool:
        return transfer.transfer.source_node_id == self.node_id

    def recv_parameter(self, param: Parameter|int|str) -> Parameter:
        if isinstance(param, Parameter):
            return self._params_interface.get(param.name)
        return self._params_interface.get(param)

    def set_param(self, param: Parameter) -> bool:
        """
        """
        if self._params_interface.set(param):
            logger.info(f"Set parameter {param.name} for node {self.node_id}")
            return True
        logger.error(f"Failed to set parameter {param.name} for node {self.node_id}. Param does not exist")
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

    def recieve_message(self, msg_type: DronecanMessages, timeout_sec=0.03) -> DronecanMessages.Message|None:
        if msg_type not in self.rx_mes_types:
            logger.error(f"Message type {msg_type} is not in {self.node_id} rx_mes_types")
            return None
        res = self.interface_node.sub_once(msg_type.dronecan_type, timeout_sec=timeout_sec, msg_filter=self.msg_filter)
        if res is None:
            logger.error(f"No message {msg_type.dronecan_type} from node {self.node_id}")
            return None
        logger.debug(f"Got message {msg_type.name} from node {self.node_id}")
        return msg_type.from_message(msg=res.message)

    def send_message(self, msg: DronecanMessages.Message, timeout_sec=0.03) -> bool:
        if type(msg) not in self.tx_mes_types:
            logger.error(f"Message type {type(msg)} is not in {self.node_id} tx_mes_types")
            return False
        self.interface_node.pub(msg.to_dronecan(), timeout_sec=timeout_sec)
        return True

    def get_message_types(self) -> Dict[str, DronecanMessages.Message]:
        """Retuns node supported message types
            @return: Dict with tx and rx message types
        """
        return {"tx": self.tx_mes_types, "rx": self.rx_mes_types}

class ICENode(NodeInterface):
    """Class for communication with ICE nodes"""
    name = "ice_node"
    unique_param = 'air.cmd'
    command_type_param_name = 'air.cmd'

    rx_mes_types = [DronecanMessages.NodeStatus,
                    DronecanMessages.ICEReciprocatingStatus,
                    DronecanMessages.FuelTankStatus,
                    DronecanMessages.ActuatorStatus,
                    DronecanMessages.ESCStatus]
    tx_mes_types = [DronecanMessages.ESCRPMCommand]

    class AirCommandTypes(enum.IntEnum):
        RAWCOMMAND      = 0,
        ARRAYCOMMAND    = 1

    def __init__(self, destination_node_id: int, node: DronecanNode|None = None):
        super().__init__(destination_node_id=destination_node_id, node=node)

class MiniNode(NodeInterface):
    """Class for communication with mini nodes"""
    name = "mini_node"
    unique_param = "pwm.cmd_type"

    rx_mes_types = [DronecanMessages.NodeStatus,
                    DronecanMessages.ActuatorStatus,
                    DronecanMessages.ESCStatus]
    tx_mes_types = [DronecanMessages.ActuatorCommand,
                    DronecanMessages.ArrayCommand,
                    DronecanMessages.ESCRawCommand]

    class FeedbackTypes(enum.IntEnum):
        DISABLED    = 0,
        FREQ_1_HZ   = 1,
        FREQ_10_HZ  = 2

    class CommandTypes(enum.IntEnum):
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
                logger.info(f"MiniNode {self.node_id} has IMU")
                self.tx_mes_types.append(DronecanMessages.RawImu)
                self.tx_mes_types.append(DronecanMessages.ImuVibrations)
                return
        logger.info(f"MiniNode {self.node_id} does not have IMU")

    def change_pwm_channel(self, channel: int, pwm_num: int) -> None:
        self._params_interface.set(params=Parameter(name=f"pwm{pwm_num}.ch", value=channel))

    def change_feedback_type(self, type: int| FeedbackTypes):
        self._params_interface.set(params=Parameter(name=f"feedback.type", value=type))

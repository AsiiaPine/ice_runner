
from ast import List
import asyncio
import logging
import os
import sys
import time
from typing import Any, Dict
from mqtt_client import RaspberryMqttClient

sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '../dronecan_communication')))
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from dronecan_communication.nodes_communicator import NodesCommunicator, NodeType
import dronecan_communication.DronecanMessages as messages
logger = logging.getLogger(__name__)

RAWCmdStep = 0.1
RPMCmdStep = 0.1

class DronecanCommander:
    stop_message = messages.ESCRPMCommand(command=[0, 0, 0])
    current_rpm_command = messages.ESCRPMCommand(command=[0, 0, 0])

    @classmethod
    def connect(cls, logging_interval_s: int = 10) -> None:
        cls.communicator = NodesCommunicator(mes_timeout_sec=2.0)
        while cls.communicator.configurator.get_nodes_list(node_type=NodeType.ICE) is None:
            print("No ice nodes found, waiting")
            cls.communicator.find_nodes()

        cls.ice_node = cls.communicator.configurator.nodes[NodeType.ICE][0]

        mini_nodes = cls.communicator.configurator.nodes[NodeType.MINI]
        if len(mini_nodes) > 0:
            cls.mini_node = mini_nodes[0]
        else:
            cls.mini_node = None

        cls.logging_interval_s = logging_interval_s
        cls.last_logging_time = 0
        cls.states: Dict[str, Dict[str, messages.Message]] = {"ice": {}, "mini": {}}
        if cls.ice_node is None:
            print("No ice nodes found")

    @classmethod
    def set_parameters(cls, parameters: Dict[str, Any]) -> None:
        cls.communicator.set_parameters_to_nodes(parameters, NodeType.ICE)

    @classmethod
    def start(cls) -> None:
        print("Start")
        cls.current_rpm_command = messages.ESCRPMCommand(command=[1000, 1000, 1000])
        cls.current_raw_command = messages.ESCRawCommand(command=[1000, 1000, 1000])
        cls.communicator.broadcast_message(message=cls.current_rpm_command, timeout_sec=2.0)
        cls.communicator.broadcast_message(message=cls.current_raw_command, timeout_sec=2.0)

    @classmethod
    def stop(cls) -> None:
        print("Stop")
        cls.communicator.send_message(message=cls.stop_message, node_id=39, timeout_sec=2.0)

    @classmethod
    def run(cls) -> None:
        while True:
            cls.set_setpoint(RaspberryMqttClient.setpoint_command)
            cls.communicator.broadcast_message(message=cls.current_rpm_command)
            cls.communicator.broadcast_message(message=cls.current_raw_command)
            print(cls.current_raw_command)
            print(cls.current_rpm_command)
            cls.get_states()
            RaspberryMqttClient.publish_state(cls.states)
            # await asyncio.sleep(0.1)

    @classmethod
    def set_setpoint(cls, rpm: int) -> None:
        cls.current_raw_command = messages.ESCRawCommand(command=[rpm, rpm, rpm])
        cls.current_rpm_command = messages.ESCRPMCommand(command=[rpm, rpm, rpm])

    # @classmethod
    # def reduce_setpoint(cls) -> None:
    #     curr_raw_cmd = cls.current_raw_command.command[0] - RAWCmdStep
    #     curr_prm_cmd = cls.current_prm_command.command[0] - RPMCmdStep
    #     cls.current_raw_command = messages.ESCRawCommand(command=[curr_raw_cmd, curr_raw_cmd, curr_raw_cmd])
    #     cls.current_prm_command = messages.ESCRPMCommand(command=[curr_prm_cmd, curr_prm_cmd, curr_prm_cmd])

    # @classmethod
    # def increase_setpoint(cls) -> None:
    #     curr_raw_cmd = cls.current_raw_command.command[0] + RAWCmdStep
    #     curr_prm_cmd = cls.current_prm_command.command[0] + RPMCmdStep
    #     cls.current_raw_command = messages.ESCRawCommand(command=[curr_raw_cmd, curr_raw_cmd, curr_raw_cmd])
    #     cls.current_prm_command = messages.ESCRPMCommand(command=[curr_prm_cmd, curr_prm_cmd, curr_prm_cmd])

    @classmethod
    def set_raw_command(cls, value: int) -> None:
        cls.current_rpm_command = messages.ESCRawCommand(command=[value, value, value])

    @classmethod
    def get_states(cls):
        for mess_type in cls.ice_node.rx_mes_types:
            message = cls.ice_node.recieve_message(mess_type, timeout_sec=0.03)
            if message is not None:
                cls.states["ice"][mess_type.name] = message

        if cls.mini_node is None:
            return
        for mess_type in cls.mini_node.rx_mes_types:
            message = cls.ice_node.recieve_message(mess_type, timeout_sec=0.03)
            if message is not None:
                cls.states["mini"][mess_type.name] = message

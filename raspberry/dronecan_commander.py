
from ast import List
import logging
import os
import sys
import time
from typing import Any, Dict

sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '../dronecan_communication')))
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from dronecan_communication.nodes_communicator import NodesCommunicator, NodeType
import dronecan_communication.DronecanMessages as messages
logger = logging.getLogger(__name__)

class DronecanCommander:
    def __init__(self, logging_interval_s: int = 10) -> None:
        self.communicator = NodesCommunicator(mes_timeout_sec=2.0)
        while self.communicator.configurator.get_nodes_list(node_type=NodeType.ICE) is None:
            print("No ice nodes found, waiting")
            self.communicator.find_nodes()

        # self.communicator.set_parameters_to_nodes(parameters_dir="default_params")
        self.stop_message = messages.ESCRPMCommand(command=[0, 0, 0])
        self.current_prm_command = self.stop_message
        self.ice_node = self.communicator.configurator.nodes[NodeType.ICE][0]

        mini_nodes = self.communicator.configurator.nodes[NodeType.MINI]
        if len(mini_nodes) > 0:
            self.mini_node = mini_nodes[0]
        else:
            self.mini_node = None

        self.logging_interval_s = logging_interval_s
        self.last_logging_time = 0
        self.states: Dict[str, List[str]] = {"ice": {}, "mini": {}}
        if self.ice_node is None:
            print("No ice nodes found")

    def set_parameters(self, parameters: Dict[str, Any]) -> None:
        self.communicator.set_parameters_to_nodes(parameters, NodeType.ICE)

    def start(self) -> None:
        print("Start")
        self.current_prm_command = messages.ESCRPMCommand(command=[1000, 1000, 1000])
        self.communicator.broadcast_message(message=self.current_prm_command, timeout_sec=2.0)

    def stop(self) -> None:
        print("Stop")
        self.communicator.send_message(message=self.stop_message, node_id=39, timeout_sec=2.0)

    async def run(self) -> None:
        self.communicator.broadcast_message(message=self.current_prm_command)
        await self.get_states()

    def set_rpm(self, rpm: int) -> None:
        self.current_prm_command = messages.ESCRPMCommand(command=[rpm, rpm, rpm])

    def set_raw_command(self, value: int) -> None:
        self.current_prm_command = messages.ESCRawCommand(command=[value, value, value])

    async def get_states(self):
        for mess_type in self.ice_node.rx_mes_types:
            message = self.ice_node.recieve_message(mess_type, timeout_sec=0.03)
            if message is not None:
                self.states["ice"][mess_type.name] = message.to_dict()

        if self.mini_node is None:
            return
        for mess_type in self.mini_node.rx_mes_types:
            message = self.ice_node.recieve_message(mess_type, timeout_sec=0.03)
            if message is not None:
                self.states["mini"][mess_type.name] = message.to_dict()
        # self.states = self.states

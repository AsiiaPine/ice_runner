
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
        self.ice_node = self.communicator.configurator.get_nodes_list(node_type=NodeType.ICE)[0]
        self.mini_nodes = self.communicator.configurator.get_nodes_list(node_type=NodeType.MINI)[0]
        self.logging_interval_s = logging_interval_s
        self.last_logging_time = 0
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

    def run(self) -> None:
        self.communicator.broadcast_message(message=self.current_prm_command)
        ice_messages = self.communicator.get_ice_nodes_states()
        mini_messages = self.communicator.get_mini_nodes_states()
        for message in ice_messages:
            if isinstance(message, messages.NodeStatus):
                print(f"Ice node status: {message.to_dict()}")

        for message in mini_messages:
            if isinstance(message, messages.NodeStatus):
                print(f"Mini node status: {message.to_dict()}")
        if time.time() - self.last_logging_time > self.logging_interval_s:
            self.last_logging_time = time.time()
            logger.info(f"Ice nodes statuses:\n\t{[ice_message.to_dict() for ice_message in ice_messages]}")
            logger.info(f"Mini nodes statuses:\n\t{[mini_message.to_dict() for mini_message in mini_messages]}")
            logger.info(f"current PRM command: {self.current_prm_command.to_dict()}")
        self.ice_messages = ice_messages
        self.mini_messages = mini_messages

    def set_rpm(self, rpm: int) -> None:
        self.current_prm_command = messages.ESCRPMCommand(command=[rpm, rpm, rpm])

    def set_raw_command(self, value: int) -> None:
        self.current_prm_command = messages.ESCRawCommand(command=[value, value, value])

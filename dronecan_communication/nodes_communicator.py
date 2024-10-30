import logging
import os
from typing import Any, List
from nodes_configurator import NodesConfigurator, NodesParametersParser
from DronecanMessages import Message, NodeStatus
from nodes_types import NodeType

logger = logging.getLogger(__name__)

class NodesCommunicator:
    def __init__(self, mes_timeout_sec: float = 0.03, find_nodes_timeout_sec: float = 1.0):
        self.configurator = NodesConfigurator()
        logger.info("Finding nodes")
        self.configurator.find_nodes(find_nodes_timeout_sec)
        self.mes_timeout = mes_timeout_sec

    def send_message(self, message: Message, node_id: int, timeout_sec: float = 0.03) -> bool:
        """Send message with check if the message will be received by the node based on its type"""
        node = self.configurator.get_node(node_id)
        return node.send_message(message, timeout_sec=timeout_sec)

    def broadcast_message(self, message: Message, timeout_sec: float = 0.03) -> bool:
        """Send message to all nodes"""
        self.configurator.node.pub(message.to_dronecan(), timeout_sec=timeout_sec)

    def get_ice_nodes_states(self)-> List[Message]:
        messages:List[Message] = []
        for ice_node in self.configurator.nodes[NodeType.ICE]:
            for mes_type in ice_node.rx_mes_types:
                message = ice_node.recieve_message(mes_type, timeout_sec=self.mes_timeout)
                if message is None:
                    logger.info(f"No message {mes_type} from node {ice_node.node_id}")
                    continue
                messages.append(ice_node.recieve_message(mes_type, timeout_sec=self.mes_timeout))
        return messages

    def get_mini_nodes_states(self) -> List[Message]:
        messages: List[Message] = []
        for mini_node in self.configurator.nodes[NodeType.MINI]:
            for mes_types in mini_node.rx_mes_types:
                message = mini_node.recieve_message(mes_types, timeout_sec=self.mes_timeout)
                if message is None:
                    logger.info(f"No message {mes_types} from node {mini_node.node_id}")
                    continue
                messages.append(mini_node.recieve_message(mes_types, timeout_sec=self.mes_timeout))
        return messages

    def set_parameters_to_nodes(self, parameters_dir: str, nodes_ids: List[int]= []) -> None:
        """Parse directory with parameters and set them to nodes from nodes_ids list. File name should contain node type. Example: ice.yml"""
        absolute_path = os.path.dirname(os.path.abspath(__file__))
        files_dir = absolute_path + "/" + parameters_dir
        files = os.listdir(files_dir)
        for file in files:
            if file.endswith(".yml") or file.endswith(".yaml"):
                node_type = NodeType.UNKNOWN
                if file.startswith("min"):
                    node_type = NodeType.MINI
                elif file.startswith("ice"):
                    node_type = NodeType.ICE
                else:
                    logger.error(f"Unknown nodetype in file {files_dir}/{file}. Please, specify nodetype in file name. Example: ice.yml")
                    continue
                parser = NodesParametersParser(files_dir+"/"+file)
                params = parser.convert_parameters_to_dronecan()
                needed_nodes = self.configurator.get_nodes_list(node_type)
                for node in needed_nodes:
                    if node.node_id in nodes_ids or len(nodes_ids) == 0:
                        if node.set_params(params) < len(params):
                            logger.error(f"Failed to set parameters for node {node.node_id}")
                        else:
                            logger.info(f"Set parameters for node {node.node_id}")

# TODO: add tests
# TODO: remove main
if __name__ == "__main__":
    communicator = NodesCommunicator(mes_timeout_sec=1.0)
    communicator.set_parameters_to_nodes(parameters_dir="default_params", nodes_ids=[39, 42])
    ice_states = communicator.get_ice_nodes_states()
    mini_states = communicator.get_mini_nodes_states()
    print("Got states:")
    print(f"Ice states: {len(ice_states)}")
    print(f"Mini states: {len(mini_states)}")
    for ice_state in ice_states:
        if isinstance(ice_state, NodeStatus):
            print("ICE state dict:", ice_state.to_dict())
    for mini_state in mini_states:
        if isinstance(mini_state, NodeStatus):
            print("Mini state dict:", mini_state.to_dict())

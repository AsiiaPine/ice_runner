import os
from typing import Any, List
from nodes_configurator import NodesConfigurator, NodesParametersParser
from DronecanMessages import Message, NodeStatus
from logging_configurator import get_logger
from nodes_types import NodeType

logger = get_logger(__name__)

class NodesCommunicator:
    def __init__(self, mes_timeout_sec: float = 0.03):
        self.configurator = NodesConfigurator()
        self.configurator.find_nodes()
        self.mes_timeout = mes_timeout_sec

    def send_message(self, message: Message, node_id: int, timeout_sec: float = 0.03) -> bool:
        node = self.configurator.get_node(node_id)
        return node.send_message(message, timeout_sec=timeout_sec)

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

    def set_parameters_to_nodes(self, parameters_dir: str, nodes_ids: List[int]) -> None:
        """Parse directory with parameters and set them to nodes from nodes_ids list. File name should contain node type. Example: ice.yml"""
        absolute_path = os.path.dirname(os.path.abspath(__file__))
        files_dir = absolute_path + "/" + parameters_dir
        files = os.listdir(files_dir)
        for file in files:
            if file.endswith(".yml") or file.endswith(".yaml"):
                if file.startswith("min"):
                    parser = NodesParametersParser(files_dir+"/"+file)
                    params = parser.convert_parameters_to_dronecan()
                    needed_nodes = self.configurator.get_nodes_list(NodeType.MINI)
                    for node in needed_nodes:
                        if node.node_id in nodes_ids:
                            if node.set_params(params) < len(params):
                                logger.error(f"Failed to set parameters for node {node.node_id}")
                            logger.info(f"Set parameters for node {node.node_id}")

                elif file.startswith("ice"):
                    parser = NodesParametersParser(files_dir + "/" + file)
                    params = parser.convert_parameters_to_dronecan()
                    needed_nodes = self.configurator.get_nodes_list(NodeType.ICE)
                    for node in needed_nodes:
                        if node.node_id in nodes_ids:
                            if node.set_params(params) < len(params):
                                logger.error(f"Failed to set parameters for node {node.node_id}")
                            logger.info(f"Set parameters for node {node.node_id}")

                else:
                    logger.error(f"Unknown nodetype in file {files_dir}/{file}. Please, specify nodetype in file name. Example: ice.yml")


# TODO: add tests
# TODO: remove main
if __name__ == "__main__":
    communicator = NodesCommunicator(mes_timeout_sec=2.0)
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

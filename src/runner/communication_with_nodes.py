import os
from typing import List
from configurator import NodesConfigurator, NodesParametersParser
from logging_configurator import get_logger
from nodes_types import NodeType

logger = get_logger(__name__)

class NodesCommunicator:
    def __init__(self, mes_timeout_sec: float = 0.03):
        self.configurator = NodesConfigurator()
        self.configurator.find_nodes()
        self.mes_timeout = mes_timeout_sec

    def get_ice_nodes_states(self):
        for ice_node in self.configurator.nodes[NodeType.ICE]:
            for mes_type in ice_node.rx_mes_types:
                print(ice_node.recieve_message(mes_type, timeout_sec=self.mes_timeout))

    def get_mini_nodes_states(self):
        for mini_node in self.configurator.nodes[NodeType.MINI]:
            for mes_types in mini_node.rx_mes_types:
                print(mini_node.recieve_message(mes_types, timeout_sec=self.mes_timeout))

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
                            node.set_params(params)

                elif file.startswith("ice"):
                    parser = NodesParametersParser(files_dir + "/" + file)
                    params = parser.convert_parameters_to_dronecan()
                    needed_nodes = self.configurator.get_nodes_list(NodeType.ICE)
                    for node in needed_nodes:
                        if node.node_id in nodes_ids:
                            node.set_params(params)
                else:
                    logger.error(f"Unknown nodetype in file {files_dir}/{file}. Please, specify nodetype in file name. Example: ice.yml")


# TODO: add tests
# TODO: remove main
if __name__ == "__main__":
    communicator = NodesCommunicator(mes_timeout_sec=2.0)
    communicator.set_parameters_to_nodes(parameters_dir="default_params", nodes_ids=[39])
    communicator.get_ice_nodes_states()
    communicator.get_mini_nodes_states()

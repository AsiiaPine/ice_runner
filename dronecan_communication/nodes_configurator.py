#!/usr/bin/env python3
# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import logging
import yaml
from os import path
from typing import Any, Dict, List
import dronecan
from raccoonlab_tools.dronecan.utils import ParametersInterface, NodeFinder, Parameter
from raccoonlab_tools.dronecan.global_node import DronecanNode
from nodes_types import ICENode, MiniNode, NodeInterface, NodeType

logger = logging.getLogger(__name__)

class NodesParametersParser:
    def __init__(self, file_path: str):
        self.parameters = {}
        with open(file_path, 'r') as file:
            self.parameters = yaml.safe_load(file)

    def convert_parameters_to_dronecan(self) -> List[Parameter]:
        parameters_list = []
        for name, data in self.parameters.items():
            parameters_list.append(Parameter(name=name, value=data["value"]))
        return parameters_list

    def convert_dict_to_params(params: Dict[str, Any]) -> List[Parameter]:
        parameters = []
        for param in params.keys():
            parameters.append(Parameter(name=param, value=params[param]))
        return parameters

class NodesConfigurator:
    """
        Class for finding nodes and working with their parameters
    """
    def __init__(self) -> None:
        self.nodes: Dict[NodeType, List[NodeInterface]] = {}
        self.node_types = {NodeType.ICE: ICENode, NodeType.MINI: MiniNode}
        for node_type in NodeType:
            self.nodes[node_type] = []
        self.node = DronecanNode()
        self.nodes_sniffer = NodeFinder(self.node.node)

    def find_nodes(self, timeout_sec: float = 1.0) -> None:
        """Find nodes and check their types, save them to approptiate lists"""

        node_ids = self.nodes_sniffer.find_online_nodes(timeout_sec)

        for node_id in node_ids:
            print(f"Start getting params of {node_id}")
            node_type = NodesConfigurator.check_node_type(node_id)

            if node_type >= NodeType.UNKNOWN.value:
                print(f"Unknown node type: {node_id}, skip")
            else:
                self.nodes[node_type].append(self.node_types[node_type](node_id, node=self.node))
        for node_type in NodeType:
            print(f"Found {node_type.name} nodes: {len(self.nodes[node_type])}")
        self.node.node.mode = dronecan.uavcan.protocol.NodeStatus().MODE_OPERATIONAL

    def get_nodes_list(self, node_type: NodeType| None = None) -> List[MiniNode]|List[ICENode]:
        """Get list of nodes of the specified type, if node_type is None, return list of all nodes"""
        if node_type is None:
            nodes = []
            for node_type in NodeType:
                nodes.append(self.nodes[node_type])
            return nodes
        if node_type >= NodeType.UNKNOWN.value:
            raise Exception(f"Unknown node type: {node_type}")
        return self.nodes[node_type]

    def get_node_params(self, node_id: int) -> Dict[str, Any]:
        for node in self.get_nodes_list():
            if node.node_id == node_id:
                return node.parameters

    def set_parameters_to_nodes(self, parameters: List[Parameter]|Dict[str, Any],
                                        node_type: NodeType| None = None) -> int:
        """The function sets parameters to dronecan nodes of the specified type
            :param parameters: List of dronecan parameters or dictionary with parameters in format {name: {value : ...}}
            :param node_type: Type of nodes to set parameters
            :return: Number of parameters that were set successfully
        """
        if isinstance(parameters, dict):
            parameters = self.convert_dict_to_params(parameters)
        nodes_list = self.get_nodes_list(node_type)
        success = 0
        for node in nodes_list:
            success += node.set_params(parameters)
        return success

    def set_parameters_to_node(self, parameters: List[Parameter]|Dict[str, Any],
                                        node_id: int) -> int:
        if isinstance(parameters, dict):
            parameters = self.convert_dict_to_params(parameters)
        node = self.get_node(node_id)
        return node.set_params(parameters)

    def convert_dict_to_params(self, params: Dict[str, Any]) -> List[Parameter]:
        parameters = []
        for param in params.keys():
            parameters.append(Parameter(name=param, value=params[param]))
        return parameters

    def check_node_type(node_id: int) -> NodeType:
        """Check node type by unique for each node type parameter"""
        params_interface = ParametersInterface(target_node_id=node_id)
        params = params_interface.get_all()
        if sum([1 for param in params if param.name == MiniNode.unique_param]):
            return NodeType.MINI
        if sum([1 for param in params if param.name == ICENode.unique_param]):
            return NodeType.ICE
        return NodeType.UNKNOWN

    def print_all_params(self, node_id) -> None:
        print(f"Node {node_id} parameters:")
        for node in self.get_nodes_list():
            if node.node_id == node_id:
                for param in node.parameters.keys():
                    print(f"{param}: {node.parameters[param]}")

    def get_node(self, node_id: int) -> NodeInterface:
        for node_type in NodeType:
            for node in self.nodes[node_type]:
                if node.node_id == node_id:
                    return node

# TODO: add tests
# TODO: remove main
if __name__ == "__main__":
    mini_nodes_parameters_path = path.dirname(path.abspath(__file__)) + '/default_params/mini_node.yml'
    param_parser = NodesParametersParser(mini_nodes_parameters_path)
    configurator = NodesConfigurator()
    configurator.find_nodes()
    configurator.print_all_params(39)
    configurator.set_parameters_to_nodes(param_parser.convert_parameters_to_dronecan(), NodeType.MINI)
    print(configurator.set_parameters_to_nodes([Parameter(name="air.cmd", value=1)], NodeType.ICE))

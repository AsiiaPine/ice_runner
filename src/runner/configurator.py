#!/usr/bin/env python3
# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

from typing import Any, Dict, List
import dronecan
from raccoonlab_tools.dronecan.utils import ParametersInterface, NodeFinder, Parameter
from raccoonlab_tools.dronecan.global_node import DronecanNode
from raccoonlab_tools.dronecan.utils import ParametersInterface
from nodes_types import ICENode, MiniNode, NodeType

class NodesConfigurator:
    """
        Class for finding nodes and working with their parameters
    """
    def __init__(self) -> None:
        self.ice_nodes:  List[ICENode]    = []
        self.min_nodes:  List[MiniNode]   = []
        self.node = DronecanNode()
        self.nodes_sniffer = NodeFinder(self.node.node)
        self.node.node.mode = dronecan.uavcan.protocol.NodeStatus().MODE_OPERATIONAL

    def find_nodes(self, timeout_sec: float = 1.0) -> None:
        """Find nodes and check their types, save them to approptiate lists"""

        node_ids = self.nodes_sniffer.find_online_nodes(timeout_sec)

        for node_id in node_ids:
            print(f"Start getting params of {node_id}")
            node_type = NodesConfigurator.check_node_type(node_id)

            if node_type == NodeType.ICE:
                self.ice_nodes.append(ICENode(node_id, node=self.node))
            elif node_type == NodeType.MINI:
                self.min_nodes.append(MiniNode(node_id, node=self.node))
            else:
                print(f"Unknown node type: {node_id}")
        print(f"Found ice nodes: {len(self.ice_nodes)}")
        print(f"Found mini nodes: {len(self.min_nodes)}")

    def get_nodes_list(self, node_type: NodeType| None = None) -> List[MiniNode]|List[ICENode]:
        if node_type is None:
            return self.ice_nodes + self.min_nodes
        if node_type == NodeType.ICE:
            return self.ice_nodes
        elif node_type == NodeType.MINI:
            return self.min_nodes
        else:
            raise Exception(f"Unknown node type: {node_type}")

    def get_node_params(self, node_id: int) -> Dict[str, Any]:
        for node in self.get_nodes_list():
            if node.node_id == node_id:
                return node.parameters

    def set_parameters_to_nodes(self, parameters: List[Parameter]|Dict[str, Any],
                                        node_type: NodeType| None = None) -> int:
        if isinstance(parameters, dict):
            parameters = self.convert_dict_to_params(parameters)
        nodes_list = self.get_nodes_list(node_type)
        success = 0
        for node in nodes_list:
            success += node.set_params(parameters)
        return success

    def convert_dict_to_params(self, params: Dict[str, Any]) -> List[Parameter]:
        parameters = []
        for param in params.keys():
            parameters.append(Parameter(name=param, value=params[param]))
        return parameters

    def check_node_type(node_id: int) -> NodeType:
        """Check node type by its parameters"""
        params_interface = ParametersInterface(target_node_id=node_id)
        params = params_interface.get_all()
        if sum([1 for param in params if param.name == MiniNode.unique_param]):
            return NodeType.MINI
        if sum([1 for param in params if param.name == ICENode.unique_param]):
            return NodeType.ICE
        return NodeType.UNKNOWN

    def print_all_params(self, node_id) -> None:
        for node in self.get_nodes_list():
            if node.node_id == node_id:
                for param in node.parameters.keys():
                    print(f"{param}: {node.parameters[param]}")

# TODO: add tests
# TODO: remove main
if __name__ == "__main__":
    configurator = NodesConfigurator()
    configurator.find_nodes()
    configurator.print_all_params(39)
    print(configurator.set_parameters_to_nodes([Parameter(name="air.cmd", value=1)], NodeType.ICE))

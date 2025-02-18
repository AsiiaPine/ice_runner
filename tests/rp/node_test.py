import asyncio
import subprocess
import logging
import os
import sys
from threading import Event, Thread
from functools import partial
import time
from unittest.mock import mock_open

import pytest
from raspberry.can_control.node import CanNode, start_dronecan_handlers, stop_dronecan_handlers
from typing import Any, Callable, Dict, List, Tuple
import dronecan
from dronecan.node import Node
from raccoonlab_tools.dronecan.utils import ParametersInterface
from raccoonlab_tools.dronecan.global_node import DronecanNode
from raccoonlab_tools.common.device_manager import DeviceManager


logger = logging.getLogger()
logger.level = logging.INFO

@pytest.hookimpl
def pytest_configure(config):
    logging_plugin = config.pluginmanager.get_plugin("logging-plugin")

    # Change color on existing log level
    logging_plugin.log_cli_handler.formatter.add_color_level(logging.INFO, "cyan")

    # Add color to a custom log level (a custom log level `SPAM` is already set up)
    logging_plugin.log_cli_handler.formatter.add_color_level(logging.SPAM, "blue")


class BaseTest():
    def setup_method(self, test_method):
        CanNode.messages = {}
        CanNode.connect()
        start_dronecan_handlers()
        self.stream_handler = logging.StreamHandler(sys.stdout)
        logger.addHandler(self.stream_handler)

    def setup_node(self):
        self.node: DronecanNode = DronecanNode(node_id=66)
        self.node.node = dronecan.make_node('slcan0',
                                            node_id=66,
                                            bitrate=1000000,
                                            baudrate=1000000)
        self.node.node.health = 0
        self.node.node.mode = 0

    def run_node(self, timeout=None, tasks: List[Tuple[Callable, float]]=None):
        """The function runs the node, with the possibility to add tasks to be
            executed every t_out seconds"""
        start_time = time.time()
        self.setup_node()

        cooldown = 1
        if tasks is not None:
            cooldown = min(cooldown, min([t_out for _, t_out in tasks]))
            tasks_last_calls = [0] * len(tasks)
        while time.time() - start_time < timeout:
            self.node.node.spin(0)
            self.node.node.node_id
            if tasks is not None:
                for i, task in enumerate(tasks):
                    func, t_out = task
                    if time.time() - tasks_last_calls[i] > t_out:
                        tasks_last_calls[i] = time.time()
                        func(self.node)
            time.sleep(cooldown)

    def teardown_method(self, test_method):
        logger.removeHandler(self.stream_handler)
        stop_dronecan_handlers()
        CanNode.messages = {}

    def create_a_callback(self):
        def callback(transfer_event: dronecan.node.TransferEvent,
                     event: Event, expected_values: Dict[str, Any]=None):
            if transfer_event.transfer.source_node_id != CanNode.node.node_id:
                return
            if expected_values is None:
                event.set()
                return

            message = transfer_event.message

            for key, value in expected_values.items():
                mes_value = getattr(message, key)
                if isinstance(value, Dict):
                    for sub_key, sub_value in value.items():
                        real_value = getattr(mes_value, sub_key)
                        assert real_value == sub_value
                    continue
                else:
                    assert real_value == expected_values[key]
            event.set()
        return callback

    def add_callback(self, callback_called, dronecan_type: str, expected_msg=None):
        callback = self.create_a_callback()

        self.node.node.add_handler(
            dronecan_type, callback
            # , event=callback_called, expected_value=expected_msg)
        )

    async def wait_for_bool(self, expression: Callable, timeout: float = 3) -> bool:
        start_time = time.time()
        while (not expression()) and (time.time() - start_time < timeout):
            CanNode.spin()
            await asyncio.sleep(0.1)
        if expression():
            return True
        return False

class TestNode(BaseTest):
    def test_candump(self, mocker):
        candump_task = mocker.patch('raspberry.can_control.node.CanNode.__run_candump__')
        candump_task.return_value = 42
        mocker.patch('raspberry.can_control.node.CanNode.__stop_candump__')
        CanNode.change_file()
        CanNode.__run_candump__.assert_called()
        CanNode.__stop_candump__.assert_called_once()

    @pytest.mark.asyncio
    async def test_node_status_sub(self):
        timeout = 4
        self.node_thread = Thread(target = self.run_node, args = (timeout,))
        self.node_thread.start()
        res: bool = await self.wait_for_bool(lambda: len(CanNode.messages) > 0, timeout=timeout)
        self.node_thread.join()
        logging.info(f"{res}, {CanNode.node.node_id}")
        assert res

    @pytest.mark.asyncio
    async def test_raw_imu_sub(self):
        timeout = 4
        tasks = [(lambda x: x.node.broadcast(dronecan.uavcan.equipment.ahrs.RawIMU()), 0.5)]
        self.node_thread = Thread(target = self.run_node, args = (timeout, tasks))
        self.node_thread.start()
        res: bool = await self.wait_for_bool(
            lambda: "uavcan.equipment.ahrs.RawIMU" in CanNode.messages, timeout=timeout)
        self.node_thread.join()
        logging.info(CanNode.messages)
        assert res

    @pytest.mark.asyncio
    async def test_fuel_tank_status_sub(self):
        timeout = 4
        tasks = [(lambda x: x.node.broadcast(dronecan.uavcan.equipment.ice.FuelTankStatus()), 0.5)]
        self.node_thread = Thread(target = self.run_node, args = (timeout, tasks))
        self.node_thread.start()
        res: bool = await self.wait_for_bool(
            lambda: "uavcan.equipment.ice.FuelTankStatus" in CanNode.messages, timeout=timeout)
        self.node_thread.join()
        logging.info(CanNode.messages)
        assert res

    @pytest.mark.asyncio
    async def test_ice_recipirocating_status_sub(self):
        timeout = 4
        tasks = [(lambda x: x.node.broadcast(dronecan.uavcan.equipment.ice.reciprocating.Status()), 0.5)]
        self.node_thread = Thread(target = self.run_node, args = (timeout, tasks))
        self.node_thread.start()
        res: bool = await self.wait_for_bool(
            lambda: "uavcan.equipment.ice.reciprocating.Status" in CanNode.messages, timeout=timeout)
        self.node_thread.join()
        logging.info(f"{CanNode.messages}, {CanNode.node.node_id}")
        assert res

def main():
    # cmd = ["pytest", os.path.abspath(__file__), "-v", '-W', 'ignore::DeprecationWarning']
    # cmd += sys.argv[1:]
    # sys.exit(subprocess.call(cmd))

    pytest_args = [
        '--verbose',
        '-W', 'ignore::DeprecationWarning',
        os.path.abspath(__file__),
        # other tests here...
    ]
    pytest.main(pytest_args)
if __name__ == "__main__":
    main()

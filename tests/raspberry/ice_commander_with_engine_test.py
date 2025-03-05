import asyncio
import logging
import os
import sys
import time

import pytest
from typing import Any, Callable, List, Tuple
import dronecan
from raccoonlab_tools.dronecan.global_node import DronecanNode
from raccoonlab_tools.common.device_manager import DeviceManager

from common.RunnerState import RunnerState
from common.IceRunnerConfiguration import IceRunnerConfiguration
from raspberry.can_control.node import (CanNode, start_dronecan_handlers,
                                                   stop_dronecan_handlers)
from raspberry.can_control.ice_commander import ICECommander
from common.EngineState import EngineState, EngineStatus
from StoppableThread import StoppableThread

logger = logging.getLogger()
logger.level = logging.INFO

class EngineSimulator:
    def __init__(self) -> None:
        self.recip_status_message: Any = dronecan.uavcan.equipment.ice.reciprocating.Status()
        self.recip_status_message.state = EngineState.STOPPED.value
        self.recip_status_message.engine_speed_rpm = 0
        self.recip_status_message.oil_temperature = 0
        self.recip_status_message.engine_load_percent = 0
        self.recip_status_message.throttle_position_percent = 0
        self.recip_status_message.intake_manifold_temperature = 0
        self.recip_status_message.oil_pressure = 0
        self.recip_status_message.fuel_pressure = 0
        self.recip_status_message.integration_interval = 0
        self.recip_status_message.available_fuel_volume_cm3 = 0
        self.recip_status_message.available_fuel_volume_percent = 0
        self.node: DronecanNode = DronecanNode(node_id=66)
        self.node.node = dronecan.make_node(DeviceManager.get_device_port(),
                                            node_id=66,
                                            bitrate=1000000,
                                            baudrate=1000000)
    def set_state(self,value: int) -> None:
        self.recip_status_message.state = value

    def on_actuator_command(self, event: dronecan.node.TransferEvent) -> None:
        pass

    def on_esc_raw_command(self, event: dronecan.node.TransferEvent) -> None:
        pass

    def add_handlers(self):
        self.node.node.add_handler(dronecan.uavcan.equipment.actuator.Command, self.on_actuator_command)
        self.node.node.add_handler(dronecan.uavcan.equipment.esc.RawCommand, self.on_esc_raw_command)

    def fit_to_config(self, config: IceRunnerConfiguration) -> None:
        self.recip_status_message.engine_speed_rpm = config.rpm
        self.recip_status_message.oil_temperature = config.min_temperature
        self.recip_status_message.engine_load_percent = config.gas_throttle
        self.recip_status_message.throttle_position_percent = config.air_throttle
        self.recip_status_message.intake_manifold_temperature = config.min_vin_voltage
        self.recip_status_message.oil_pressure = config.min_vin_voltage
        self.recip_status_message.fuel_pressure = config.min_fuel_volume
        self.recip_status_message.available_fuel_volume_percent = config.min_fuel_volume

    def run(self, timeout: float=0, tasks: List[Tuple[Callable, float]]=None, cooldown: float=1):
        start_time = time.time()

        if tasks is not None:
            cooldown = min(cooldown, min([t_out for _, t_out in tasks]))
            tasks_last_calls = [0] * len(tasks)
        while time.time() - start_time < timeout:
            self.node.node.spin(0)
            if tasks is not None:
                assert isinstance(tasks, list)
                logger.info(f"tasks: {tasks}")
                for i, (func, t_out) in enumerate(tasks):
                    if time.time() - tasks_last_calls[i] > t_out:
                        tasks_last_calls[i] = time.time()
                        func(self)
            logging.info(
            f"{CanNode.status.state.name}, {self.recip_status_message.state}")
            time.sleep(cooldown)

class BaseTest():
    def setup_method(self, test_method):
        CanNode.status = EngineStatus()
        self.engine_simulator: EngineSimulator = EngineSimulator()
        self.generate_config_dict()
        self.config = IceRunnerConfiguration(dict_conf=self.config_dict)
        self.commander: ICECommander = ICECommander(self.config)
        self.stream_handler = logging.StreamHandler(sys.stdout)
        logger.addHandler(self.stream_handler)

    def generate_config_dict(self):
        config = {}
        for name in IceRunnerConfiguration.attribute_names:
            config[name] = {}
            for component in IceRunnerConfiguration.components:
                config[name][component] = ""
            config[name]["type"] = "int"
            config[name]["value"] = 0
        self.config_dict = config

    def teardown_method(self, test_method):
        logger.removeHandler(self.stream_handler)
        stop_dronecan_handlers()

    async def wait_for_bool(self, expression: Callable, timeout: float = 3) -> bool:
        start_time = time.time()
        while (not expression()) and (time.time() - start_time < timeout):
            await self.commander.spin()
            await asyncio.sleep(0.1)
        if expression():
            return True
        return False

    async def spin_engine_with_tasks(self, engine_node_tasks: List[Tuple[Callable, float]],
                              tested_expression: Callable,timeout: float = 3) -> None:
        self.engine_thread = StoppableThread(
                                        target = self.engine_simulator.run,
                                        kwargs = {"timeout": timeout, "tasks": engine_node_tasks})
        self.engine_thread.start()
        res: bool = await self.wait_for_bool(
            tested_expression, timeout=timeout)
        self.engine_thread.join()
        self.engine_thread.stop()
        logging.info(f"res {res}, tested_expression: {tested_expression()}")
        return res

    def setup_cannode(self, mocker):
        mocker.patch("raspberry.can_control.node.CanNode.change_file")
        mocker.patch("raspberry.can_control.node.CanNode.run_candump")
        mocker.patch("raspberry.can_control.node.CanNode.stop_candump")
        mocker.patch("raspberry.can_control.node.safely_write_to_file")
        CanNode.connect()
        start_dronecan_handlers()
        CanNode.spin()
        return mocker

    def mock_required(self, mocker):
        mocker.patch("builtins.open")
        mocker.patch('os.path.join', return_value = "")
        mocker.patch('os.makedirs')
        mocker.patch("paho.mqtt.client.Client.publish")
        return mocker

class TestStateUpdate(BaseTest):
    @pytest.mark.asyncio()
    async def test_connection(self, mocker):
        mocker = self.setup_cannode(mocker)
        mocker = self.mock_required(mocker)
        res = await self.wait_for_bool(
            lambda: self.commander.state_controller.state > RunnerState.NOT_CONNECTED)
        assert res == False
        timeout = 4
        self.commander.state_controller.state = RunnerState.NOT_CONNECTED
        res = await self.spin_engine_with_tasks(None,
                        lambda: self.commander.state_controller.state == RunnerState.NOT_CONNECTED,
                        timeout=timeout)
        assert res

        tasks = [(lambda x: x.node.node.broadcast(x.recip_status_message), 1)]
        res = await self.spin_engine_with_tasks(tasks,
                        lambda: self.commander.state_controller.state != RunnerState.NOT_CONNECTED,
                        timeout=timeout)
        assert res

class TestNotConnectedState(BaseTest):
    def setup_method(self, test_method):
        super().setup_method(test_method)
        self.timeout = 2
        self.commander.state_controller.state = RunnerState.NOT_CONNECTED

    @pytest.mark.asyncio()
    async def test_not_connected_state(self, mocker):
        mocker = self.mock_required(mocker)
        mocker = self.setup_cannode(mocker)
        CanNode.status.state = EngineState.NOT_CONNECTED
        res = await self.spin_engine_with_tasks(None,
                        lambda: self.commander.state_controller.state == RunnerState.NOT_CONNECTED,
                        timeout=self.timeout)
        assert res

    @pytest.mark.asyncio()
    async def test_stopped_state(self, mocker):
        mocker = self.setup_cannode(mocker)
        mocker = self.mock_required(mocker)
        self.engine_simulator.recip_status_message.state = EngineState.STOPPED.value
        tasks = [(lambda x: x.node.node.broadcast(x.recip_status_message), 1)]
        res = await self.spin_engine_with_tasks(tasks,
                            lambda: self.commander.state_controller.state == RunnerState.STOPPED,
                            timeout=self.timeout)
        assert res

    @pytest.mark.asyncio()
    async def test_running_state(self, mocker):
        mocker = self.setup_cannode(mocker)
        mocker = self.mock_required(mocker)
        self.engine_simulator.recip_status_message.state = EngineState.RUNNING.value
        tasks = [(lambda x: x.node.node.broadcast(x.recip_status_message), 1)]
        res = await self.spin_engine_with_tasks(tasks,
                            lambda: self.commander.state_controller.state == RunnerState.STOPPING,
                            timeout=self.timeout)
        assert res

    @pytest.mark.asyncio()
    async def test_starting_state(self, mocker):
        mocker = self.setup_cannode(mocker)
        mocker = self.mock_required(mocker)
        self.engine_simulator.recip_status_message.state = EngineState.WAITING.value
        tasks = [(lambda x: x.node.node.broadcast(x.recip_status_message), 2)]
        res = await self.spin_engine_with_tasks(tasks,
                            lambda: self.commander.state_controller.state == RunnerState.STOPPING,
                            timeout=self.timeout)
        assert res


class TestStoppedState(BaseTest):
    def setup_method(self, test_method):
        super().setup_method(test_method)
        self.timeout = 10
        self.commander.state_controller.state = RunnerState.STOPPED

    @pytest.mark.asyncio()
    async def test_not_connected_state(self, mocker):
        mocker = self.mock_required(mocker)
        mocker = self.setup_cannode(mocker)

        logging.info(
            f"res: {self.commander.state_controller.state.name}, {CanNode.status.state.name}, {self.engine_simulator.recip_status_message.state}")
        CanNode.status.state = EngineState.NOT_CONNECTED
        res = await self.spin_engine_with_tasks(None,
                        lambda: self.commander.state_controller.state == RunnerState.NOT_CONNECTED,
                        timeout=self.timeout)
        logging.info(
            f"res: {self.commander.state_controller.state.name}, {CanNode.status.state.name}, {self.engine_simulator.recip_status_message.state}")
        assert res

# class TestRunningState(TestNotConnectedState):
#     def setup_method(self, test_method):
#         super().setup_method(test_method)
#         self.timeout = 10
#         self.commander.state_controller.state = RunnerState.RUNNING

#     @pytest.mark.asyncio()
#     async def test_stopped_state(self, mocker):
#         mocker = self.mock_required(mocker)
#         mocker = self.setup_cannode(mocker)
#         self.engine_simulator.recip_status_message.state = EngineState.STOPPED.value
#         tasks = [(lambda x: x.node.node.broadcast(x.recip_status_message), 1),
#                  (lambda x: (x.set_state(EngineState.STOPPED.value)), 0.5)]
#         res = await self.spin_engine_with_tasks(tasks,
#                             lambda: self.commander.state_controller.state == RunnerState.STARTING,
#                             timeout=self.timeout)
#         assert res

def main():
    pytest_args = [
        '--verbose',
        '-W', 'ignore::DeprecationWarning',
        os.path.abspath(__file__),
    ]
    pytest.main(pytest_args)
if __name__ == "__main__":
    main()

import asyncio
import logging
import os
import secrets
import sys
import time

import pytest
from typing import Callable, List, Tuple
import dronecan
from raccoonlab_tools.common.device_manager import DeviceManager
from raccoonlab_tools.dronecan.global_node import DronecanNode
from common.ICEState import ICEState, EngineState
from raspberry.can_control.node import (CanNode,
                                                   start_dronecan_handlers, stop_dronecan_handlers)
from StoppableThread import StoppableThread


logger = logging.getLogger()
logger.level = logging.INFO

@pytest.hookimpl
def pytest_configure(config):
    logging_plugin = config.pluginmanager.get_plugin("logging-plugin")

    # Change color on existing log level
    logging_plugin.log_cli_handler.formatter.add_color_level(logging.INFO, "cyan")


class BaseTest():
    def setup_method(self, test_method):
        CanNode.messages = {}

        self.stream_handler = logging.StreamHandler(sys.stdout)
        logger.addHandler(self.stream_handler)

    def setup_node(self):
        self.node: DronecanNode = DronecanNode(node_id=66)
        self.node.node = dronecan.make_node(DeviceManager.get_device_port(),
                                            node_id=66,
                                            bitrate=1000000,
                                            baudrate=1000000)
        self.node.node.health = 0
        self.node.node.mode = 0

    def setup_can_node(self, mocker):
        mocker.patch("raspberry.can_control.node.CanNode.change_file")
        mocker.patch("raspberry.can_control.node.dump_msg")
        mocker.patch("raspberry.can_control.node.CanNode.save_file")

        CanNode.connect()
        start_dronecan_handlers()

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

    async def wait_for_bool(self, expression: Callable, timeout: float = 3, mocker = None) -> bool:
        start_time = time.time()
        while (not expression()) and (time.time() - start_time < timeout):
            CanNode.spin()
            await asyncio.sleep(0.1)
        if expression():
            return True
        return False

    async def spin_nodes_with_tasks(self, node_tasks: List[Tuple[Callable, float]],
                              tested_expression: Callable,timeout: float = 3,
                              mocker = None) -> None:
        self.node_thread = StoppableThread(target = self.run_node, args = (0.1, node_tasks))
        self.node_thread.start()
        res: bool = await self.wait_for_bool(
            tested_expression, timeout=timeout, mocker=mocker)
        self.node_thread.join()
        self.node_thread.stop()
        logging.info(f"res {res}, tested_expression: {tested_expression()}")
        return res

class TestSubscriptions(BaseTest):
    @pytest.mark.asyncio
    async def test_node_status_sub(self, mocker):
        self.setup_can_node(mocker)

        timeout = 10
        tasks = [(lambda x: x.node.broadcast(dronecan.uavcan.protocol.NodeStatus()), 0.5)]
        res = await self.spin_nodes_with_tasks(tasks,
                            lambda : "uavcan.protocol.NodeStatus" in CanNode.messages,
                            timeout=timeout, mocker=mocker)
        assert res

    @pytest.mark.asyncio
    @pytest.mark.dependency()
    async def test_raw_imu_sub(self, mocker):
        self.setup_can_node(mocker)

        timeout = 4
        tasks = [(lambda x: x.node.broadcast(dronecan.uavcan.equipment.ahrs.RawIMU()), 0.5)]
        res = await self.spin_nodes_with_tasks(tasks,
                            lambda : "uavcan.equipment.ahrs.RawIMU" in CanNode.messages,
                            timeout=timeout)
        assert res

    @pytest.mark.asyncio
    @pytest.mark.dependency()
    async def test_fuel_tank_status_sub(self, mocker):
        self.setup_can_node(mocker)

        timeout = 4
        tasks = [(lambda x: x.node.broadcast(dronecan.uavcan.equipment.ice.FuelTankStatus()), 0.5)]
        res = await self.spin_nodes_with_tasks(tasks,
                            lambda: "uavcan.equipment.ice.FuelTankStatus" in CanNode.messages,
                            timeout=timeout)
        logging.info(f"{CanNode.messages}, {CanNode.node.node_id}")
        assert res

    @pytest.mark.dependency()
    @pytest.mark.asyncio
    async def test_ice_reciprocating_status_sub(self, mocker):
        self.setup_can_node(mocker)

        tasks = [(lambda x: x.node.broadcast(dronecan.uavcan.equipment.ice.reciprocating.Status()), 0.5)]
        timeout = 4
        res = await self.spin_nodes_with_tasks(tasks,
                            lambda: "uavcan.equipment.ice.reciprocating.Status" in CanNode.messages,
                            timeout=timeout)
        logging.info(f"{CanNode.messages}, {CanNode.node.node_id}")
        assert res

class TestResipUpdate(BaseTest):
    @pytest.mark.dependency(depends=["TestSubscriptions::test_ice_reciprocating_status_sub"])
    @pytest.mark.asyncio
    async def test_ice_state_update(self, mocker):
        self.setup_can_node(mocker)
        assert CanNode.state.ice_state == EngineState.NOT_CONNECTED
        timeout = 4
        tasks = [(lambda x: x.node.broadcast(dronecan.uavcan.equipment.ice.reciprocating.Status()),
                  0.5)]
        res = await self.spin_nodes_with_tasks(tasks,
                                   lambda: CanNode.state.ice_state > EngineState.NOT_CONNECTED,
                                   timeout=timeout)
        assert res

    @pytest.mark.dependency(depends=["TestResipUpdate::test_ice_state_update"])
    @pytest.mark.asyncio
    async def test_ice_state_mapping(self, mocker):
        self.setup_can_node(mocker)
        assert CanNode.state.ice_state == EngineState.NOT_CONNECTED
        timeout = 2
        state = EngineState.STOPPED
        tasks = [(lambda x: x.node.broadcast(dronecan.uavcan.equipment.ice.reciprocating.Status(state=state.value)), 0.5)]
        res = await self.spin_nodes_with_tasks(tasks,
                                   lambda: CanNode.state.ice_state == state,
                                   timeout=timeout)
        assert res
        state = EngineState.RUNNING
        tasks = [(lambda x: x.node.broadcast(dronecan.uavcan.equipment.ice.reciprocating.Status(state=state.value)), 0.5)]
        res = await self.spin_nodes_with_tasks(tasks,
                                   lambda: CanNode.state.ice_state==state,
                                   timeout=timeout)
        assert res


    @pytest.mark.dependency(depends=["TestResipUpdate::test_ice_state_mapping"])
    @pytest.mark.asyncio
    async def test_rpm_mapping(self, mocker):
        self.setup_can_node(mocker)

        CanNode.state.rpm = 1001
        timeout = 2
        rpm = secrets.randbelow(1000)
        tasks = [(
            lambda x: x.node.broadcast(
                dronecan.uavcan.equipment.ice.reciprocating.Status(engine_speed_rpm=rpm)), 0.5)]
        res = await self.spin_nodes_with_tasks(tasks,
                                   lambda: CanNode.state.rpm == rpm,
                                   timeout=timeout)
        assert res

    @pytest.mark.dependency(depends=["TestResipUpdate::test_ice_state_mapping"])
    @pytest.mark.asyncio
    async def test_temp_mapping(self, mocker):
        self.setup_can_node(mocker)

        CanNode.state.temp = 101
        timeout = 2
        temp = secrets.randbelow(100)
        tasks = [(lambda x: x.node.broadcast(dronecan.uavcan.equipment.ice.reciprocating.Status(oil_temperature=temp)), 0.5)]
        res = await self.spin_nodes_with_tasks(tasks,
                                   lambda: CanNode.state.temp != temp,
                                   timeout=timeout)
        assert res

    @pytest.mark.asyncio
    @pytest.mark.dependency(depends=["TestResipUpdate::test_ice_state_mapping"])
    async def test_full_ice_reciprocating(self, mocker):
        self.setup_can_node(mocker)
        status_mes = dronecan.uavcan.equipment.ice.reciprocating.Status(
            ecu_index=0,
            state=1,
            engine_speed_rpm=secrets.randbelow(1000),
            atmospheric_pressure_kpa=secrets.randbelow(1000),
            engine_load_percent=secrets.randbelow(1000),
            throttle_position_percent=secrets.randbelow(1000),
            oil_temperature=secrets.randbelow(1000),
            coolant_temperature=secrets.randbelow(1000),
            spark_plug_usage=0,
            estimated_consumed_fuel_volume_cm3=secrets.randbelow(1000),
            intake_manifold_temperature=secrets.randbelow(1000),
            intake_manifold_pressure_kpa=secrets.randbelow(1000),
            oil_pressure=secrets.randbelow(1000))

        tasks = [(lambda x: x.node.broadcast(status_mes), 0.5)]

        def _check_with_assert(x: ICEState,
                               y: dronecan.uavcan.equipment.ice.reciprocating.Status) -> bool:
            assert x.air_throttle==y.throttle_position_percent
            assert x.gas_throttle==y.engine_load_percent
            assert x.temp==y.oil_temperature
            assert x.ice_state==y.state
            assert x.rpm==y.engine_speed_rpm
            assert x.current==y.intake_manifold_temperature
            assert x.voltage_in==y.oil_pressure
            assert x.voltage_out==y.fuel_pressure
            return True

        def _check(x: ICEState, y: dronecan.uavcan.equipment.ice.reciprocating.Status) -> bool:
            try:
                return _check_with_assert(x, y)
            except AssertionError:
                return False

        timeout = 2
        res = await self.spin_nodes_with_tasks(tasks,
                                   lambda: _check(CanNode.state, status_mes),
                                   timeout=timeout)
        assert _check_with_assert(CanNode.state, status_mes)

class TestFulelTankUpdate(BaseTest):
    @pytest.mark.dependency(depends=["TestSubscriptions::test_fuel_tank_status_sub"])
    @pytest.mark.asyncio
    async def test_fuel_level_mapping(self, mocker):
        self.setup_can_node(mocker)

        CanNode.state.fuel_level_percent = 101
        timeout = 2
        fuel_lvl = secrets.randbelow(100)
        tasks = [(
            lambda x: x.node.broadcast(
                dronecan.uavcan.equipment.ice.FuelTankStatus(
                    available_fuel_volume_percent=fuel_lvl)), 0.5)]
        res = await self.spin_nodes_with_tasks(tasks,
                                   lambda: CanNode.state.fuel_level_percent == fuel_lvl,
                                   timeout=timeout)
        assert res

class TestRawIMUUpdate(BaseTest):
    @pytest.mark.dependency(depends=["TestSubscriptions::test_raw_imu_sub"])
    @pytest.mark.asyncio
    async def test_raw_imu_mapping(self, mocker):
        self.setup_can_node(mocker)

        CanNode.has_imu = False
        CanNode.state.rec_imu = False
        CanNode.state.vibration = 1001
        timeout = 2
        vibration = secrets.randbelow(1000)
        tasks = [(
            lambda x: x.node.broadcast(
                dronecan.uavcan.equipment.ahrs.RawIMU(integration_interval=vibration)), 0.5)]
        res = await self.spin_nodes_with_tasks(tasks,
                                   lambda: CanNode.state.vibration == vibration,
                                   timeout=timeout)
        assert res
        assert CanNode.state.rec_imu
        assert CanNode.has_imu


def main():
    pytest_args = [
        '--verbose',
        '-W', 'ignore::DeprecationWarning',
        os.path.abspath(__file__),
    ]
    pytest.main(pytest_args)

if __name__ == "__main__":
    main()

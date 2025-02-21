import asyncio
import logging
import os
import sys
import time

import pytest
from typing import Any, Callable, Dict, List, Tuple
import dronecan
from raccoonlab_tools.dronecan.global_node import DronecanNode
from raccoonlab_tools.common.device_manager import DeviceManager

from common.RunnerState import RunnerState
from common.IceRunnerConfiguration import IceRunnerConfiguration
from raspberry.can_control.node import CanNode, start_dronecan_handlers, stop_dronecan_handlers
from raspberry.can_control.ice_commander import ICECommander
from common.ICEState import RecipState
from StoppableThread import StoppableThread

logger = logging.getLogger()
logger.level = logging.INFO

class EngineSimulator:
    def __init__(self) -> None:
        self.recip_status_message: Any = dronecan.uavcan.equipment.ice.reciprocating.Status()
        self.recip_status_message.state = RecipState.STOPPED.value
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

    def run(self, timeout: float=0, cooldown: float=1,tasks: List[Tuple[Callable, float]]=None):
        start_time = time.time()

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
                        func(self)
            time.sleep(cooldown)


class BaseTest():
    def setup_method(self, test_method):
        CanNode.messages = {}
        CanNode.connect()
        start_dronecan_handlers()
        self.engine_simulator: EngineSimulator = EngineSimulator()
        self.stream_handler = logging.StreamHandler(sys.stdout)
        logger.addHandler(self.stream_handler)
        self.generate_config_dict()
        self.config = IceRunnerConfiguration(dict_conf=self.config_dict)
        self.commander: ICECommander = ICECommander(self.config)

    def generate_config_dict(self):
        config = {}
        for name in IceRunnerConfiguration.attribute_names:
            config[name] = {}
            for component in IceRunnerConfiguration.components:
                config[name][component] = ""
            config[name]["type"] = "int"
            config[name]["value"] = 1
        self.config_dict = config

    def teardown_method(self, test_method):
        logger.removeHandler(self.stream_handler)
        stop_dronecan_handlers()
        CanNode.messages = {}

    async def wait_for_bool(self, expression: Callable, timeout: float = 3) -> bool:
        start_time = time.time()
        while (not expression()) and (time.time() - start_time < timeout):
            await self.commander.spin()
            await asyncio.sleep(0.1)
        if expression():
            return True
        return False

class TestStateUpdate(BaseTest):
    @pytest.mark.asyncio
    async def test_connection(self):
        res = await self.wait_for_bool(lambda: self.commander.run_state > RunnerState.NOT_CONNECTED)
        assert res == False
        timeout = 4
        engine_thread = StoppableThread(target = self.engine_simulator.run, args = (timeout,))
        engine_thread.start()
        self.commander.run_state = RunnerState.NOT_CONNECTED
        res = await self.wait_for_bool(
            lambda: self.commander.run_state == RunnerState.NOT_CONNECTED, timeout=timeout)

        engine_thread.join()
        engine_thread.stop()

        assert res

        self.commander.run_state = RunnerState.NOT_CONNECTED
        tasks = [(lambda x: x.node.node.broadcast(x.recip_status_message), 0.5)]
        engine_thread = StoppableThread(target = self.engine_simulator.run, args = (timeout, 0.1,tasks))
        engine_thread.start()
        res = await self.wait_for_bool(
            lambda: self.commander.run_state != RunnerState.NOT_CONNECTED, timeout=timeout)
        engine_thread.join()
        engine_thread.stop()
        engine_thread
        logger.info(CanNode.state.ice_state)
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

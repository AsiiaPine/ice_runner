import asyncio
import logging
import os
import time

import pytest
from typing import Callable
import dronecan

import ice_runner
from common.RunnerState import RunnerState
from common.IceRunnerConfiguration import IceRunnerConfiguration
import raspberry
from raspberry.can_control.node import ICE_AIR_CHANNEL, CanNode
from raspberry.can_control.ice_commander import ICECommander
from common.ICEState import ICEState, RecipState

logger = logging.getLogger()
logger.level = logging.INFO


class BaseTest():
    def setup_method(self, test_method):
        self.make_config()
        CanNode.state = ICEState()
        CanNode.air_cmd = dronecan.uavcan.equipment.actuator.Command(
                                            actuator_id=ICE_AIR_CHANNEL, command_value=0)
        CanNode.cmd = dronecan.uavcan.equipment.esc.RawCommand(cmd=[0]*(ICE_AIR_CHANNEL + 1))
        self.config = IceRunnerConfiguration(dict_conf=self.config_dict)
        self.commander: ICECommander = ICECommander(self.config)
        self.runner_state = RunnerState.STOPPED
        self.prev_state = RunnerState.STOPPED
        self.start_time = 0
        self.commander.state_controller.prev_waiting_state_time = 0

    def make_config(self):
        config = {}
        for name in IceRunnerConfiguration.attribute_names:
            config[name] = {}
            for component in IceRunnerConfiguration.components:
                config[name][component] = ""
            config[name]["type"] = "int"
            config[name]["value"] = 0
        config["mode"]["value"] = 1
        self.config_dict = config

    async def wait_for_bool(self, expression: Callable, timeout: float = 3) -> bool:
        start_time = time.time()
        while (not expression()) and (time.time() - start_time < timeout):
            await self.commander.spin()
            await asyncio.sleep(0.1)
        if expression():
            return True
        return False

class TestSetState(BaseTest):
    @pytest.mark.dependency()
    def test_not_connected(self):
        self.commander.state_controller.state = RunnerState.NOT_CONNECTED
        self.commander.set_state(False)
        assert self.commander.state_controller.state == RunnerState.NOT_CONNECTED
        self.commander.set_state(True)
        assert self.commander.state_controller.state == RunnerState.NOT_CONNECTED

    @pytest.mark.dependency(depends=["TestSetState::test_not_connected"])
    def test_just_connected(self):
        CanNode.state.ice_state = RecipState.STOPPED
        self.commander.state_controller.state = RunnerState.NOT_CONNECTED
        self.commander.set_state(False)
        assert self.commander.state_controller.state == RunnerState.STOPPED

    # @pytest.mark.dependency(depends=["TestSetState::test_not_connected"])
    def test_start_again(self, mocker):
        mocker.patch('raspberry.can_control.node.CanNode.save_file')
        mocker.patch('raspberry.can_control.ice_commander.ICECommander.send_log')
        mocker.patch('raspberry.can_control.node.CanNode.change_file')
        mocker.patch('raspberry.mqtt.handlers.MqttClient.publish_stop_reason')

        CanNode.state.ice_state = RecipState.STOPPED
        self.commander.state_controller.state = RunnerState.RUNNING

        # if conditions are not exceeded, try to start again
        self.commander.set_state(False)
        assert self.commander.state_controller.state == RunnerState.STARTING

        # if conditions are exceeded, stop the runner
        self.commander.state_controller.state = RunnerState.RUNNING
        self.commander.set_state(True)
        assert self.commander.state_controller.state == RunnerState.STOPPING

    @pytest.mark.dependency(depends=["TestSetState::test_not_connected"])
    def test_cond_exceeded_stopped(self, mocker):
        mocker.patch('raspberry.can_control.ice_commander.ICECommander.stop')
        # does not affect stopped runner
        CanNode.state.ice_state = RecipState.STOPPED
        self.commander.state_controller.state = RunnerState.NOT_CONNECTED
        self.commander.set_state(True)
        raspberry.can_control.ice_commander.ICECommander.stop.assert_not_called()
        assert self.commander.state_controller.state == RunnerState.STOPPED

    def test_cond_exceeded_running(self, mocker):
        # affects running runner
        mocker.patch('raspberry.can_control.node.CanNode.save_file')
        mocker.patch('raspberry.can_control.ice_commander.ICECommander.send_log')
        mocker.patch('raspberry.can_control.node.CanNode.change_file')
        mocker.patch('raspberry.mqtt.client.MqttClient.publish_stop_reason')

        CanNode.state.ice_state = RecipState.STOPPED
        self.commander.state_controller.state = RunnerState.RUNNING
        self.commander.set_state(True)
        assert self.commander.state_controller.state == RunnerState.STOPPING

    def test_cond_exceeded_starting(self, mocker):
        # affects running runner
        mocker.patch('raspberry.can_control.node.CanNode.save_file')
        mocker.patch('raspberry.can_control.ice_commander.ICECommander.send_log')
        mocker.patch('raspberry.can_control.node.CanNode.change_file')
        mocker.patch('raspberry.mqtt.client.MqttClient.publish_stop_reason')

        CanNode.state.ice_state = RecipState.STOPPED
        self.commander.state_controller.state = RunnerState.STARTING
        self.commander.set_state(True)
        assert self.commander.state_controller.state == RunnerState.STOPPING

    def test_cond_exceeded_fault(self, mocker):
        # does not affect fault runner
        mocker.patch('raspberry.can_control.ice_commander.ICECommander.stop')
        CanNode.state.ice_state = RecipState.STOPPED
        self.commander.state_controller.state = RunnerState.FAULT
        self.commander.set_state(True)
        raspberry.can_control.ice_commander.ICECommander.stop.assert_not_called()
        assert self.commander.state_controller.state == RunnerState.FAULT

    def test_ice_waiting_run_state_not_connected(self, mocker):
        mocker.patch('raspberry.can_control.node.CanNode.save_file')
        mocker.patch('raspberry.can_control.ice_commander.ICECommander.send_log')
        mocker.patch('raspberry.can_control.node.CanNode.change_file')
        mocker.patch('raspberry.mqtt.client.MqttClient.publish_stop_reason')

        self.commander.state_controller.state = RunnerState.NOT_CONNECTED
        CanNode.state.ice_state = RecipState.WAITING
        assert self.commander.state_controller.prev_waiting_state_time == 0
        self.commander.set_state(False)
        assert self.commander.state_controller.state == RunnerState.STARTING
        assert self.commander.state_controller.prev_waiting_state_time != 0

    def test_ice_waiting_run_state_stopped(self):
        self.commander.state_controller.state = RunnerState.STOPPED
        CanNode.state.ice_state = RecipState.WAITING
        assert self.commander.state_controller.prev_waiting_state_time == 0
        self.commander.set_state(False)
        assert self.commander.state_controller.state == RunnerState.STARTING
        assert self.commander.state_controller.prev_waiting_state_time != 0

    def test_ice_waiting_run_state_running(self):
        self.commander.state_controller.state = RunnerState.RUNNING
        CanNode.state.ice_state = RecipState.WAITING
        assert self.commander.state_controller.prev_waiting_state_time == 0
        self.commander.set_state(False)
        assert self.commander.state_controller.state == RunnerState.STARTING
        assert self.commander.state_controller.prev_waiting_state_time != 0

    def test_ice_waiting_run_state_starting(self):
        self.commander.state_controller.state = RunnerState.STARTING
        CanNode.state.ice_state = RecipState.WAITING
        assert self.commander.state_controller.prev_waiting_state_time == 0
        self.commander.set_state(False)
        assert self.commander.state_controller.state == RunnerState.STARTING
        assert self.commander.state_controller.prev_waiting_state_time != 0

class TestSetCommand(BaseTest):
    def test_no_command(self):
        self.commander.state_controller.state = RunnerState.NOT_CONNECTED
        self.commander.set_command()
        assert sum(CanNode.cmd.cmd) == 0
        assert CanNode.air_cmd.command_value == -1

        self.commander.state_controller.state = RunnerState.STOPPED
        self.commander.set_command()
        assert sum(CanNode.cmd.cmd) == 0
        assert CanNode.air_cmd.command_value == -1

        self.commander.state_controller.state = RunnerState.FAULT
        self.commander.set_command()
        assert sum(CanNode.cmd.cmd) == 0
        assert CanNode.air_cmd.command_value == -1


def main():
    pytest_args = [
        '--verbose',
        '-W', 'ignore::DeprecationWarning',
        os.path.abspath(__file__),
    ]
    pytest.main(pytest_args)
if __name__ == "__main__":
    main()

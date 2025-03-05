import logging
import os
import secrets
import time

import pytest
from raspberry.can_control.EngineState import EngineStatus, EngineState
from raspberry.can_control.RunnerConfiguration import RunnerConfiguration
from common.RunnerState import RunnerState
from raspberry.can_control.RunnerStateController import RunnerStateController
from raspberry.can_control.ice_commander import ExceedanceTracker, ICERunnerMode

logger = logging.getLogger()
logger.level = logging.INFO

def test_cleanup():
    ex_tracker: ExceedanceTracker = ExceedanceTracker()
    dictionary = vars(ex_tracker)
    for item in vars(ex_tracker):
        dictionary[item] = True
    assert bool(sum(dictionary[name] for name in dictionary.keys()))
    ex_tracker.cleanup()
    assert not bool(sum(dictionary[name] for name in dictionary.keys()))

class BaseTest():
    def setup_method(self, test_method):
        self.ex_tracker: ExceedanceTracker = ExceedanceTracker()
        self.make_config()
        self.state = EngineStatus()
        self.config = RunnerConfiguration(dict_conf=self.config_dict)
        self.runner_state = RunnerStateController()
        self.runner_state.state = RunnerState.STOPPED
        self.runner_state.prev_state = RunnerState.STOPPED
        self.start_time = 0

    def make_config(self):
        config = {}
        for name in RunnerConfiguration.attribute_names:
            config[name] = {}
            for component in RunnerConfiguration.components:
                config[name][component] = ""
            config[name]["type"] = "int"
            config[name]["value"] = 0
        config["mode"]["value"] = 0
        self.config_dict = config

    def check_fuel_level(self):
        self.config.min_fuel_volume = 10
        self.state.fuel_level_percent = 100
        assert not self.ex_tracker.check(
            self.state, self.config, self.runner_state, self.start_time)
        self.state.fuel_level_percent = 0
        assert self.ex_tracker.check(
            self.state, self.config, self.runner_state, self.start_time)

    def check_vin(self):
        self.config.min_vin_voltage = 40
        self.state.voltage_in = 40
        assert not self.ex_tracker.check(
            self.state, self.config, self.runner_state, self.start_time)
        self.state.voltage_in = 0
        assert self.ex_tracker.check(
            self.state, self.config, self.runner_state, self.start_time)

    def check_temp(self):
        self.config.max_temperature = 100
        self.state.temp = 100
        assert not self.ex_tracker.check(
            self.state, self.config, self.runner_state, self.start_time)
        self.state.temp = 200
        assert self.ex_tracker.check(
            self.state, self.config, self.runner_state, self.start_time)

class TestNotStarted(BaseTest):
    def test_not_started_call(self, mocker):

        candump_task = mocker.patch(
            'raspberry.can_control.ice_commander.ExceedanceTracker.check_not_started')
        self.ex_tracker.check(self.state, self.config, self.runner_state, self.start_time)
        candump_task.assert_called_once()

    def test_not_started(self):
        self.state.state = EngineState.STOPPED
        assert not self.ex_tracker.check(
            self.state, self.config, self.runner_state, self.start_time)

    def test_fuel_level(self):
        self.check_fuel_level()

    def test_vin(self):
        self.check_vin()

    def test_temp(self):
        self.check_temp()

    def test_eng_time(self):
        assert not self.ex_tracker.check(
            self.state, self.config, self.runner_state, self.start_time)

        self.state.engaged_time = 40 * 60 * 60 # 40 hours

        assert not self.ex_tracker.check(
            self.state, self.config, self.runner_state, self.start_time)

        self.state.engaged_time = 40 * 60 * 60  + 1 # 40 hours + 1 sec

        assert self.ex_tracker.check(
            self.state, self.config, self.runner_state, self.start_time)

class TestStarting(BaseTest):
    def setup_method(self, test_method):
        super().setup_method(test_method)
        self.config = RunnerConfiguration(dict_conf=self.config_dict)
        self.runner_state.state = RunnerState.STARTING
        self.start_time = time.time()
        self.config.start_attemts = 1
        self.config.time = 10

    def test_running_call(self, mocker):
        """ExceedanceTracker should use check_running method if the state is STARTING"""
        candump_task = mocker.patch(
            'raspberry.can_control.ice_commander.ExceedanceTracker.check_running')
        self.ex_tracker.check(self.state, self.config, self.runner_state, self.start_time)
        candump_task.assert_called_once()

    def test_fuel_level(self):
        """ExceedanceTracker should always check fuel level"""
        self.check_fuel_level()

    def test_vin(self):
        """ExceedanceTracker should always check VIN"""
        self.check_vin()

    def test_temp(self):
        """ExceedanceTracker should always check temperature"""
        self.check_temp()

    def test_eng_time(self):
        """ExceedanceTracker should not check engaged time if the state is STARTING"""
        self.runner_state.prev_state = RunnerState.STARTING
        assert not self.ex_tracker.check(
            self.state, self.config, self.runner_state, self.start_time)

        self.state.engaged_time = 40 * 60 * 60 # 40 hours

        assert not self.ex_tracker.check(
            self.state, self.config, self.runner_state, self.start_time)

        self.state.engaged_time = 40 * 60 * 60  + 1 # 40 hours + 1 sec
        assert not self.ex_tracker.check(
            self.state, self.config, self.runner_state, self.start_time)

    def test_start_attempts(self):
        assert not self.ex_tracker.check(
            self.state, self.config, self.runner_state, self.start_time)
        self.runner_state.start_attempts = 2
        assert self.ex_tracker.check(
            self.state, self.config, self.runner_state, self.start_time)

    def test_time_exceeded(self):
        """ExceedanceTracker should check engaged time if the state is STARTING"""
        self.runner_state.prev_state = RunnerState.STARTING
        self.config.time = 10
        assert not self.ex_tracker.check(
            self.state, self.config, self.runner_state, self.start_time)
        self.config.time = 1
        self.start_time = time.time() - 1
        assert self.ex_tracker.check(
            self.state, self.config, self.runner_state, self.start_time)

    def test_rpm_exceeded(self):
        """ExceedanceTracker should ignore RPM if the state is STARTING"""
        self.runner_state.prev_state = RunnerState.STARTING
        self.state.rpm = 1000
        assert not self.ex_tracker.check(
            self.state, self.config, self.runner_state, self.start_time)
        self.state.rpm = 7500
        assert not self.ex_tracker.check(
            self.state, self.config, self.runner_state, self.start_time)
        self.state.rpm = 7501
        assert self.ex_tracker.check(
            self.state, self.config, self.runner_state, self.start_time)

class TestCONSTMode(BaseTest):
    def setup_method(self, test_method):
        super().setup_method(test_method)
        self.config.mode = ICERunnerMode.CONST

    def test_fuel_level(self):
        self.check_fuel_level()
    
    def test_vin(self):
        self.check_vin()

    def test_temp(self):
        self.check_temp()

    def test_time_exceeded(self):
        self.config.time = 3
        self.runner_state.state = RunnerState.RUNNING
        assert not self.ex_tracker.check(
            self.state, self.config, self.runner_state, self.start_time)
        self.start_time = time.time() - 4
        assert self.ex_tracker.check(
            self.state, self.config, self.runner_state, self.start_time)

class TestPIDMode(BaseTest):
    def setup_method(self, test_method):
        super().setup_method(test_method)
        self.config.mode = ICERunnerMode.PID
        self.config.control_pid_p = 0.1
        self.config.control_pid_i = 0.2
        self.config.control_pid_d = 0.3

    def test_fuel_level(self):
        self.check_fuel_level()
    
    def test_vin(self):
        self.check_vin()

    def test_temp(self):
        self.check_temp()

    def test_time_exceeded(self):
        self.config.time = 3
        self.runner_state.state = RunnerState.RUNNING
        assert not self.ex_tracker.check(
            self.state, self.config, self.runner_state, self.start_time)
        self.start_time = time.time() - 4
        assert self.ex_tracker.check(
            self.state, self.config, self.runner_state, self.start_time)

    def test_rpm_exceeded(self):
        self.config.rpm = secrets.randbelow(1000)
        self.state.rpm = self.config.rpm
        self.runner_state.state = RunnerState.RUNNING
        assert not self.ex_tracker.check(
            self.state, self.config, self.runner_state, self.start_time)

        self.state.rpm = self.config.rpm + 1000
        assert self.ex_tracker.check(
            self.state, self.config, self.runner_state, self.start_time)

class TestCheckMode(BaseTest):
    def setup_method(self, test_method):
        super().setup_method(test_method)
        self.config.mode = ICERunnerMode.CHECK

    def test_fuel_level(self):
        self.check_fuel_level()

    def test_vin(self):
        self.check_vin()

    def test_temp(self):
        self.check_temp()

    def test_time_exceeded(self):
        """Constant value for time 12, so config does not influence the state"""
        self.runner_state.state = RunnerState.RUNNING
        self.start_time = time.time()
        assert not self.ex_tracker.check(
            self.state, self.config, self.runner_state, self.start_time)
        self.start_time = time.time() - 4
        assert not self.ex_tracker.check(
            self.state, self.config, self.runner_state, self.start_time)
        self.start_time = time.time() - 12
        assert self.ex_tracker.check(
            self.state, self.config, self.runner_state, self.start_time)

class TestFuelPumpMode(BaseTest):
    def setup_method(self, test_method):
        super().setup_method(test_method)
        self.config.mode = ICERunnerMode.FUEL_PUMPTING

    def test_fuel_level(self):
        self.check_fuel_level()

    def test_vin(self):
        self.check_vin()

    def test_temp(self):
        self.check_temp()

    def test_time_exceeded(self):
        """Constant value for time 8, so config does not influence the state"""
        self.runner_state.state = RunnerState.RUNNING
        self.start_time = time.time()
        assert not self.ex_tracker.check(
            self.state, self.config, self.runner_state, self.start_time)
        self.start_time = time.time() - 10
        assert not self.ex_tracker.check(
            self.state, self.config, self.runner_state, self.start_time)
        self.start_time = time.time() - 30
        assert self.ex_tracker.check(
            self.state, self.config, self.runner_state, self.start_time)


def main():
    pytest_args = [
        '--verbose',
        '-W', 'ignore::DeprecationWarning',
        os.path.abspath(__file__),
    ]
    pytest.main(pytest_args)
if __name__ == "__main__":
    main()

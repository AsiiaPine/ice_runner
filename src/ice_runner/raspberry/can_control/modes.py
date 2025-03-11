"""The module defines the modes of the ICE runner"""

from enum import IntEnum
import logging
import time
from typing import Any, Dict, List, Tuple, Type
from common.RunnerState import RunnerState
from raspberry.can_control.EngineState import EngineState
from raspberry.can_control.RunnerConfiguration import RunnerConfiguration

MAX_AIR_CMD = 2000
MIN_AIR_CMD = 1000

class ICERunnerMode(IntEnum):
    """The class is used to define the mode of the ICE runner"""
    CONST = 0 # Юзер задает 30-50% тяги, и просто сразу же ее выставляем, без ПИД-регулятора.
                # Без проверки оборотов, но с проверкой температуры.
    PID = 1 # Юзер задает обороты, и мы их поддерживаем ПИД-регулятором на стороне скрипта.
    RPM = 2 # Команда на 4500 оборотов (RPMCommand) без ПИД-регулятора
                # на стороне скрипта - все на стороне платы.
    CHECK = 3 # Запуск на 8 секунд, проверка сартера
    FUEL_PUMPTING = 4 # Запуск на 60 секунд

    def get_mode_class(self, configuration: RunnerConfiguration) -> Type["BaseMode"]:
        if self == ICERunnerMode.CONST:
            return ConstMode(configuration=configuration)
        if self == ICERunnerMode.PID:
            return PIDMode(configuration=configuration)
        if self == ICERunnerMode.RPM:
            return RPMMode(configuration=configuration)
        if self == ICERunnerMode.CHECK:
            return CheckMode(configuration=configuration)
        if self == ICERunnerMode.FUEL_PUMPTING:
            return FuelPumpMode(configuration=configuration)
        raise ValueError(f"Unknown mode {self}")


class BaseMode:
    name: ICERunnerMode
    def __init__(self, configuration: RunnerConfiguration):
        self.gas_throttle = int(configuration.gas_throttle_pct * 8191 / 100)
        self.air_throttle = int((configuration.air_throttle_pct / 100)\
                            * (MAX_AIR_CMD - MIN_AIR_CMD) + MIN_AIR_CMD)

    def update_configuration(self, configuration: RunnerConfiguration) -> None:
        self.gas_throttle = int(configuration.gas_throttle_pct * 8191 / 100)
        self.air_throttle = int((configuration.air_throttle_pct / 100)\
                            * (MAX_AIR_CMD - MIN_AIR_CMD) + MIN_AIR_CMD)

    def get_command(self, run_state: RunnerState, **kwargs) -> List[int]:
        if run_state == RunnerState.RUNNING:
            return self.get_running_command(**kwargs)
        if run_state == RunnerState.STARTING:
            return self.get_starting_command(**kwargs)
        return self.get_zero_command()

    def get_running_command(self, **kwargs) -> List[int]:
        raise NotImplementedError

    def get_zero_command(self):
        return [-1, self.air_throttle]

    def get_starting_command(self, **kwargs):
        return [self.gas_throttle, self.air_throttle]

class ConstMode(BaseMode):
    name = ICERunnerMode.CONST
    def __init__(self, configuration: RunnerConfiguration):
        super().__init__(configuration)

    def get_running_command(self, **kwargs) -> List[int]:
        command = [0, 0]
        command[0] = int(self.gas_throttle)
        command[1] = self.air_throttle
        return command

class PIDMode(BaseMode):
    name = ICERunnerMode.PID
    def __init__(self, configuration: RunnerConfiguration):
        super().__init__(configuration)
        coeffs: Tuple[float, float, float] = (
                configuration.control_pid_p,
                configuration.control_pid_i,
                configuration.control_pid_d)
        max_value = 8191 * configuration.max_gas_throttle_pct / 100
        min_value = 8191 * configuration.min_gas_throttle_pct / 100
        self.pid_controller = PIDController(configuration.rpm, coeffs, max_value, min_value)

    def get_zero_command(self):
        return super().get_zero_command()

    def get_starting_command(self, rpm, engine_state: EngineState, **kwarg):
        self.pid_controller.prev_error = self.pid_controller.target_value - rpm
        self.pid_controller.prev_command = self.gas_throttle
        self.pid_controller.integral = 0
        self.pid_controller.prev_time = time.time()
        return [self.gas_throttle, self.air_throttle]

    def get_running_command(self, rpm, **kwarg) -> List[int]:
        command = [0, 0]
        command[0] = int(self.pid_controller.get_pid_command(rpm))
        command[1] = self.air_throttle
        return command

    def update_configuration(self, configuration:RunnerConfiguration):
        self.pid_controller.update_configuration(configuration=configuration)
        return super().update_configuration(configuration)

class RPMMode(BaseMode):
    name = ICERunnerMode.RPM
    def __init__(self, configuration: RunnerConfiguration):
        super().__init__(configuration)
        self.rpm = configuration.rpm

    def update_configuration(self, configuration: RunnerConfiguration):
        self.rpm = configuration.rpm
        return super().update_configuration(configuration)

class CheckMode(BaseMode):
    name = ICERunnerMode.CHECK
    def __init__(self, configuration: RunnerConfiguration):
        super().__init__(configuration)
        self.air_throttle = MAX_AIR_CMD

    def get_running_command(self, **kwargs) -> List[int]:
        return [self.gas_throttle, MAX_AIR_CMD]

class FuelPumpMode(BaseMode):
    name = ICERunnerMode.FUEL_PUMPTING
    def __init__(self, configuration: RunnerConfiguration):
        super().__init__(configuration)
        self.gas_throttle = int(0.1 * 8191)
        self.air_throttle = -1

    def get_running_command(self, **kwargs) -> List[int]:
        return [self.gas_throttle, self.air_throttle]

class PIDController:
    """Basic PID controller"""

    def __init__(self, target_value: int, coeffs: Tuple[float, float, float],
                    max_value: int = 8000, min_value: int =0) -> None:
        self.target_value = target_value
        self.coeffs: Dict[str, float] = {"kp": coeffs[0], "ki": coeffs[1], "kd": coeffs[2]}
        self.prev_time = 0
        self.prev_error = 0
        self.integral = 0
        self.prev_command = 0
        self.max_value = max_value
        self.min_value = min_value

    def get_pid_command(self, val: int) -> int:
        """The function calculates PID command. Params: val - current value"""
        dt = time.time() - self.prev_time
        error = self.target_value - val
        drpm = (error - self.prev_error) / dt
        self.integral += self.coeffs["ki"] * error * (dt)
        self.prev_time = time.time()
        self.prev_error = error
        diff_part = self.coeffs["kd"] * drpm
        int_part = self.coeffs["ki"] * self.integral
        pos_part = self.coeffs["kp"] * error
        command = self.prev_command + pos_part + diff_part + int_part
        command = min(self.max_value, max(self.min_value, command))
        self.prev_command = command
        logging.debug("PID\t-\tCommand: prev %d current %d, %d pos, %d int, %d diff",
                      self.prev_command, command, pos_part, int_part, diff_part)
        return command

    def update_configuration(self, configuration: RunnerConfiguration) -> None:
        """The function changes the coefficients of the PID controller"""
        self.coeffs: Dict[str, float] = {"kp": configuration.control_pid_p,
                                         "ki": configuration.control_pid_i,
                                         "kd": configuration.control_pid_d}
        self.max_value = 8191 * configuration.max_gas_throttle_pct / 100
        self.min_value = 8191 * configuration.min_gas_throttle_pct / 100
        self.target_value = configuration.rpm
        logging.info(
        f"PID\t-\tconfiguration updated: max value {self.max_value}, min value {self.min_value}, target {self.target_value}, coeffs {self.coeffs}")

    def cleanup(self):
        self.prev_error = 0
        self.integral = 0
        self.prev_time = 0
        self.prev_command = -1

from enum import IntEnum
import time
from typing import Any, Dict, List, Tuple, Type
from common.RunnerState import RunnerState
from common.IceRunnerConfiguration import IceRunnerConfiguration


class ICERunnerMode(IntEnum):
    """The class is used to define the mode of the ICE runner"""
    CONST = 0 # Юзер задает 30-50% тяги, и просто сразу же ее выставляем, без ПИД-регулятора.
                # Без проверки оборотов, но с проверкой температуры.
    PID = 1 # Юзер задает обороты, и мы их поддерживаем ПИД-регулятором на стороне скрипта.
    RPM = 2 # Команда на 4500 оборотов (RPMCommand) без ПИД-регулятора
                # на стороне скрипта - все на стороне платы.
    CHECK = 3 # Запуск на 8 секунд, проверка сартера
    FUEL_PUMPTING = 4 # Запуск на 60 секунд

    def get_mode_class(self, configuration: IceRunnerConfiguration) -> Type["BaseMode"]:
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
    def __init__(self, configuration: IceRunnerConfiguration):
        self.gas_throttle = configuration.gas_throttle * 8191 / 100
        self.air_throttle = int(configuration.air_throttle / 50) - 1

    def get_command(self, run_state: RunnerState, **kwargs) -> List[int]:
        if run_state == RunnerState.RUNNING:
            return self.get_running_command(**kwargs)
        if run_state == RunnerState.STARTING:
            return self.get_starting_command()
        return self.get_zero_command()

    def get_running_command(self, **kwargs) -> List[int]:
        pass

    def get_zero_command(self):
        return [0, -1]

    def get_starting_command(self):
        return [3500, (self.air_throttle / 50) - 1.0]

class ConstMode(BaseMode):
    name = ICERunnerMode.CONST
    def __init__(self, configuration: IceRunnerConfiguration):
        super().__init__(configuration)

    def get_running_command(self, **kwargs) -> List[int]:
        command = [0, 0]
        command[0] = int(self.gas_throttle)
        command[1] = self.air_throttle
        return command

class PIDMode(BaseMode):
    name = ICERunnerMode.PID
    def __init__(self, configuration: IceRunnerConfiguration):
        super().__init__(configuration)
        coeffs: Tuple[float, float, float] = (
                configuration.control_pid_p,
                configuration.control_pid_i,
                configuration.control_pid_d)
        self.pid_controller = PIDController(configuration.rpm, coeffs)

    def get_running_command(self, rpm) -> List[int]:
        command = [0, 0]
        command[0] = int(self.pid_controller.get_pid_command(rpm))
        command[1] = self.air_throttle
        return command

class RPMMode(BaseMode):
    name = ICERunnerMode.RPM
    def __init__(self, configuration: IceRunnerConfiguration):
        super().__init__(configuration)
        self.rpm = configuration.rpm

    def get_running_command(self, **kwargs) -> List[int]:
        command = [0, 0]
        command[0] = int(self.rpm)
        command[1] = self.air_throttle
        return command

class CheckMode(BaseMode):
    name = ICERunnerMode.CHECK
    def __init__(self, configuration: IceRunnerConfiguration):
        super().__init__(configuration)

    def get_running_command(self, **kwargs) -> List[int]:
        return [int(0.2 * 8191), self.air_throttle]

    def get_starting_command(self):
        return [int(0.2 * 8191), self.air_throttle]

class FuelPumpMode(BaseMode):
    name = ICERunnerMode.FUEL_PUMPTING
    def __init__(self, configuration: IceRunnerConfiguration):
        super().__init__(configuration)

    def get_running_command(self, **kwargs) -> List[int]:
        return [self.gas_throttle, -1]

    def get_starting_command(self):
        return [self.gas_throttle, -1]

class PIDController:
    """Basic PID controller"""

    def __init__(self, seeked_value: int, coeffs: Tuple[float, float, float]) -> None:
        self.seeked_value = seeked_value
        self.coeffs: Dict[str, float] = {"kp": coeffs[0], "ki": coeffs[1], "kd": coeffs[2]}
        self.prev_time = 0
        self.prev_error = 0
        self.integral = 0

    def get_pid_command(self, val: int) -> int:
        """The function calculates PID command"""
        dt = time.time() - self.prev_time
        error = self.seeked_value - val
        drpm = (error - self.prev_error) / dt
        self.integral += self.coeffs["ki"] * error * (dt)

        self.prev_time = time.time()
        self.prev_error = error
        diff_part = self.coeffs["kd"] * drpm
        int_part = self.coeffs["ki"] * self.integral
        pos_part = self.coeffs["kp"] * error
        return self.seeked_value + pos_part + diff_part + int_part

    def change_coeffs(self, coeffs: Dict[str, float]) -> None:
        """The function changes the coefficients of the PID controller"""
        self.coeffs = coeffs

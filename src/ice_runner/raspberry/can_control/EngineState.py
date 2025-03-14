# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

import copy
from enum import IntEnum
from typing import Any, Dict
import logging

logger = logging.getLogger(__name__)

class Mode(IntEnum):
    MODE_OPERATIONAL = 0
    MODE_INITIALIZATION = 1
    MODE_MAINTENANCE = 2
    MODE_SOFTWARE_UPDATE = 3
    MODE_OFFLINE = 7

class Health(IntEnum):
    HEALTH_OK = 0
    HEALTH_WARNING = 1
    HEALTH_ERROR = 2
    HEALTH_CRITICAL = 3

class EngineState(IntEnum):
    NOT_CONNECTED = -1
    STOPPED = 0
    STARTER_RUNNING = 1
    STARTER_WAITING = 2
    FAULT = 3

class EngineStatus:
    def __init__(self) -> None:
        self.state: EngineState = EngineState.NOT_CONNECTED
        self.rpm: int = 0
        self.temp: int = 0
        self.fuel_level: int = 0
        self.fuel_level_percent: int = 0
        self.gas_throttle: int = 0
        self.air_throttle: int = 0

        self.current: float = 0

        self.voltage_in: float = 0
        self.voltage_out: float = 0

        self.vibration: float = 0

        self.engaged_time: float = 0
        self.mode: Mode = Mode.MODE_OPERATIONAL
        self.health: Health = Health.HEALTH_OK
        self.rec_imu: bool = False
        self.start_attempts: int = 0

    def update_with_resiprocating_status(self, msg) -> None:
        self.state = EngineState(msg.message.state)
        self.rpm = msg.message.engine_speed_rpm
        self.temp = msg.message.oil_temperature
        self.gas_throttle = msg.message.engine_load_percent
        self.air_throttle = msg.message.throttle_position_percent
        self.current = msg.message.intake_manifold_temperature
        self.voltage_in = msg.message.oil_pressure
        self.voltage_out = msg.message.fuel_pressure

    def update_with_raw_imu(self, msg) -> None:
        self.vibration = msg.message.integration_interval
        self.rec_imu = True

    def update_with_node_status(self, msg) -> None:
        if msg.message.mode > self.mode:
            self.mode = Mode(msg.message.mode)
        if msg.message.health > self.health:
            self.health = Health(msg.message.health)
        if self.mode > Mode.MODE_SOFTWARE_UPDATE or self.health > Health.HEALTH_WARNING:
            self.state = EngineState.FAULT

    def update_with_fuel_tank_status(self, msg) -> None:
        self.fuel_level = msg.message.available_fuel_volume_cm3
        self.fuel_level_percent = msg.message.available_fuel_volume_percent

    def to_dict(self) -> Dict[str, Any]:
        vars_dict = copy.deepcopy(vars(self))

        vars_dict["state"] = self.state.name
        vars_dict["mode"] = self.mode.name
        vars_dict["health"] = self.health.name
        return vars_dict

    def get_description_dict(self):
        rpm = f"{self.rpm}"
        gas_air = f"{self.gas_throttle}% {self.air_throttle}%"
        temp = f"{round(self.temp - 273.15, 2)} °C"
        fuel_level = f"{self.fuel_level_percent}%"

        return {"RPM": rpm, "GAS/AIR": gas_air, "TEMP": temp, "FUEL level": fuel_level}

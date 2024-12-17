from enum import IntEnum
from typing import Any, Dict
import logging
import logging_configurator

logger = logging.getLogger(__name__)

ModeDict = {
    "MODE_OPERATIONAL" : 0,
    "MODE_INITIALIZATION" : 1,
    "MODE_MAINTENANCE" : 2,
    "MODE_SOFTWARE_UPDATE" : 3,
    "MODE_OFFLINE" : 7
}

HealthDict = {
    "HEALTH_OK" : 0,
    "HEALTH_WARNING" : 1,
    "HEALTH_ERROR" : 2,
    "HEALTH_CRITICAL" : 3
}

RecipStateDict = {
    "NOT_CONNECTED" : -1,
    "STOPPED" : 0,
    "RUNNING" : 1,
    "WAITING" : 2,
    "FAULT" : 3
}

class ICEState:
    def __init__(self) -> None:
        self.ice_state: int = RecipStateDict["NOT_CONNECTED"]
        self.rpm: int = None
        self.throttle: int = None
        self.temp: int = None
        self.fuel_level: int = None
        self.fuel_level_percent: int = None
        self.gas_throttle: int = None
        self.air_throttle: int = None

        self.current: float = None

        self.voltage_in: float = None
        self.voltage_out: float = None

        self.vibration: float = None

        self.engaged_time: float = None
        self.mode = ModeDict["MODE_OPERATIONAL"]
        self.health = HealthDict["HEALTH_OK"]

    def update_with_resiprocating_status(self, msg) -> None:
        logging.getLogger(__name__).info(f"UPD STATE: {msg.message.state}")
        self.ice_state = msg.message.state
        print(self.ice_state)
        self.rpm = msg.message.engine_speed_rpm
        self.throttle = msg.message.throttle_position_percent
        self.temp = msg.message.oil_temperature
        self.gas_throttle = msg.message.engine_load_percent
        self.air_throttle = msg.message.throttle_position_percent
        self.current = msg.message.intake_manifold_temperature
        self.voltage_in = msg.message.oil_pressure
        self.voltage_out = msg.message.fuel_pressure

    def update_with_raw_imu(self, msg) -> None:
        self.vibration = msg.message.integration_interval

    def update_with_node_status(self, msg) -> None:
        if msg.message.mode > self.mode.value:
            print(type(self.mode))
            print(msg.message.mode, type(msg.message.mode))
            self.mode = int(msg.message.mode)
            print(type(self.mode), "\n\n\n\n\n\n\n\n")
        if msg.message.health > self.health.value:
            self.health = int(msg.message.health)
        if self.mode > ModeDict["MODE_SOFTWARE_UPDATE"] or self.health > HealthDict["HEALTH_WARNING"]:
            self.ice_state = RecipStateDict["FAULT"]

    def update_with_fuel_tank_status(self, msg) -> None:
        self.fuel_level = msg.message.available_fuel_volume_cm3
        self.fuel_level_percent = msg.message.available_fuel_volume_percent

    def to_dict(self) -> Dict[str, Any]:
        vars_dict = vars(self)

        vars_dict["ice_state"] = self.ice_state
        vars_dict["mode"] = self.mode
        vars_dict["health"] = self.health
        return vars_dict

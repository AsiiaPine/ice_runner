import copy
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

def get_recip_state_name(state) -> str:
    if state == RecipStateDict["NOT_CONNECTED"]:
        return "NOT_CONNECTED"
    if state == RecipStateDict["STOPPED"]:
        return "STOPPED"
    if state == RecipStateDict["RUNNING"]:
        return "RUNNING"
    if state == RecipStateDict["WAITING"]:
        return "WAITING"
    if state == RecipStateDict["FAULT"]:
        return "FAULT"
    return "UNKNOWN"

def get_health_name(health: int) -> str:
    if health == HealthDict["HEALTH_OK"]:
        return "HEALTH_OK"
    if health == HealthDict["HEALTH_WARNING"]:
        return "HEALTH_WARNING"
    if health == HealthDict["HEALTH_CRITICAL"]:
        return "HEALTH_CRITICAL"
    if health == HealthDict["HEALTH_ERROR"]:
        return "HEALTH_ERROR"
    return "UNKNOWN"

def get_mode_name(mode: int) -> str:
    if mode == ModeDict["MODE_OPERATIONAL"]:
        return "MODE_OPERATIONAL"
    if mode == ModeDict["MODE_INITIALIZATION"]:
        return "MODE_INITIALIZATION"
    if mode == ModeDict["MODE_MAINTENANCE"]:
        return "MODE_MAINTENANCE"
    if mode == ModeDict["MODE_OFFLINE"]:
        return "MODE_OFFLINE"
    if mode == ModeDict["MODE_SOFTWARE_UPDATE"]:
        return "MODE_SOFTWARE_UPDATE"
    return "UNKNOWN"

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
            self.mode = int(msg.message.mode)
        if msg.message.health > self.health.value:
            self.health = int(msg.message.health)
        if self.mode > ModeDict["MODE_SOFTWARE_UPDATE"] or self.health > HealthDict["HEALTH_WARNING"]:
            self.ice_state = RecipStateDict["FAULT"]

    def update_with_fuel_tank_status(self, msg) -> None:
        self.fuel_level = msg.message.available_fuel_volume_cm3
        self.fuel_level_percent = msg.message.available_fuel_volume_percent

    def to_dict(self) -> Dict[str, Any]:
        vars_dict = copy.deepcopy(vars(self))

        vars_dict["ice_state"] = get_recip_state_name(self.ice_state)
        vars_dict["mode"] = get_mode_name(self.mode)
        vars_dict["health"] = get_health_name(self.health)
        return vars_dict

"""The script is used to define the configuration of the ICE runner"""

# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

from copy import deepcopy
from typing import Any, Dict
import yaml

class IceRunnerConfiguration:
    rpm: int = 4500
    max_temperature: int = 190 + 273.15 # Kelvin
    max_gas_throttle: int = 0
    max_vibration: float = 100
    min_fuel_volume: int = 0
    min_vin_voltage: int = 40
    time: int = 0
    report_period: int = 10
    chat_id: int = 0
    num_cells: int = 3
    setpoint_ch: int = 7
    mode: int = 0
    command: int = 0

    def __init__(self, file_path: str = None, dict_conf: Dict[str, Any] = None) -> None:
        """The function loads configuration from file or dictionary"""
        self.original_dict = None
        self.last_file_path = None
        if dict_conf is not None:
            self.from_dict(dict_conf)
            return
        if file_path is not None:
            self.from_file(file_path)
            return
        raise ValueError("No configuration provided")

    def __str__(self) -> str:
        return str(self.to_dict())

    def to_dict(self) -> Dict[str, Any]:
        dictionary = deepcopy(vars(self))
        dictionary.pop("original_dict")
        dictionary.pop("last_file_path")
        return dictionary

    def from_dict(self, conf: Dict[str, Any]) -> None:
        """The function loads configuration from dictionary"""
        self.rpm = conf["rpm"]["value"]
        self.time = conf["time"]["value"]
        self.max_temperature = conf["max_temperature"]["value"] + 273.15 # Kelvin
        self.max_gas_throttle = conf["max_gas_throttle"]["value"]
        self.report_period = conf["report_period"]["value"]
        self.max_vibration = conf["max_vibration"]["value"]
        self.min_fuel_volume = conf["min_fuel_volume"]["value"]
        self.min_vin_voltage = 0
        if "min_vin_voltage" in conf.keys():
            self.min_vin_voltage = conf["min_vin_voltage"]["value"]
        else:
            if "num_cells" in conf.keys():
                self.min_vin_voltage = conf["num_cells"]["value"] * 3.2
        self.mode = conf["mode"]["value"]
        self.command = conf["command"]["value"]

    def from_file(self, file_path: str) -> None:
        """The function loads configuration from file"""
        if file_path.split(".")[-1] not in ("yml", "yaml"):
            raise ValueError("Unsupported file format")
        with open(file_path) as file:
            conf = yaml.safe_load(file)
        self.from_dict(conf)
        self.original_dict: Dict[str, Dict[str, Any]] = conf
        self.last_file_path = file_path

    def to_file(self, file_path: str|None = None) -> None:
        """The function saves configuration to file"""
        if file_path is None:
            file_path = self.last_file_path
        if file_path is None:
            raise ValueError("No file path provided")
        self.sync_before_save()
        with open(file_path, "w", encoding="utf8") as file:
            yaml.dump(self.original_dict, file, allow_unicode=True)

    def sync_before_save(self) -> None:
        """The function is called before saving the configuration to a file"""
        if self.original_dict is None:
            return
        for name in self.original_dict:
            self.original_dict[name]["value"] = vars(self)[name]

"""The script is used to define the configuration of the ICE runner"""

# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

from copy import deepcopy
from typing import Any, Dict
import yaml

from common.algorithms import get_type_from_str

class MyDumper(yaml.SafeDumper):
    # HACK: insert blank lines between top-level objects
    # inspired by https://stackoverflow.com/a/44284819/3786245
    def write_line_break(self, data=None):
        super().write_line_break(data)

        if len(self.indents) == 1:
            super().write_line_break()

class IceRunnerConfiguration:
    """The class is used to define the configuration of the ICE runner"""
    attribute_names = ["mode", "rpm", "time", "gas_throttle_pct", "air_throttle_pct",
                       "min_gas_throttle_pct", "max_gas_throttle_pct", "report_period", "control_pid_p",
                       "control_pid_i", "control_pid_d", "max_temperature",
                       "min_fuel_volume", "min_vin_voltage", "start_attemts",
                       "max_vibration"]
    components = ["default", "help", "type", "value", "min", "max", "unit", "usage"]

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
        for attr in conf.keys():
            attr_type = conf[attr]["type"]  # Get the type specified in the YAML
            attr_value = conf[attr]["value"]
            setattr(self, attr, get_type_from_str(attr_type)(attr_value))

        for attr in self.attribute_names:
            if attr not in conf.keys():
                raise ValueError(
                    f"No configuration for {attr}. Needed attributes: {self.attribute_names}\n with components: {self.components}")
        self.original_dict: Dict[str, Dict[str, Any]] = conf

    def from_file(self, file_path: str) -> None:
        """The function loads configuration from file"""
        if file_path.split(".")[-1] not in ("yml", "yaml"):
            raise ValueError("Unsupported file format")
        with open(file_path, "r", encoding="utf-8") as file:
            conf = yaml.safe_load(file)
        self.from_dict(conf)
        self.last_file_path = file_path

    def to_file(self, file_path: str|None = None) -> None:
        """The function saves configuration to file"""
        if file_path is None:
            file_path = self.last_file_path
        if file_path is None:
            raise ValueError("No file path provided")
        self.sync_before_save()
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(yaml.dump(self.original_dict,
                                 allow_unicode=True, sort_keys=False, Dumper=MyDumper))

    def sync_before_save(self) -> None:
        """The function is called before saving the configuration to a file"""
        if self.original_dict is None:
            return
        for name in self.original_dict:
            self.original_dict[name]["value"] = vars(self)[name]

    def get_original_dict(self) -> None:
        """The function sends the original configuration to the file"""
        if self.original_dict is None:
            return
        return self.original_dict

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
    report_period: int = 600
    chat_id: int = 0
    num_cells: int = 3
    setpoint_ch: int = 7

    @classmethod
    def from_dict(cls, conf: Dict[str, Any]) -> Any:
        print(conf)
        cls.rpm = conf["rpm"] if conf["rpm"] else 4500
        cls.time = conf["time"] if conf["time"] else 0
        cls.max_temperature = conf["max_temperature"] + 273.15 if conf["max_temperature"] else 463.15  # Kelvin
        cls.max_gas_throttle = conf["max_gas_throttle"] if conf["max_gas_throttle"] else 0
        cls.report_period = conf["report_period"] if conf["report_period"] else 600
        cls.chat_id = conf["chat_id"] if "chat_id" in conf.keys() else 0
        cls.max_vibration = conf["max_vibration"] if conf["max_vibration"] else 0
        cls.min_fuel_volume = conf["min_fuel_volume"] if conf["min_fuel_volume"] else 0
        if "min_vin_voltage" in conf.keys():
            cls.min_vin_voltage = conf["min_vin_voltage"]
        else:
            if "num_cells" in conf.keys():
                cls.min_vin_voltage = conf["num_cells"] * 3.2
        return cls

    def to_dict(self) -> Dict[str, Any]:
        yaml.emitter.Emitter.prepare_tag = lambda self, tag: ''
        return yaml.dump(self, default_flow_style=False)

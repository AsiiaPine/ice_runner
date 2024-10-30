import re
configuration = {"name": 0, "value": 1}
def get_configuration_str() -> str:
    conf_str = "Configuration:\n"
    for name, value in configuration.items():
        conf_str += f"\t{name}: {value}\n"
    return conf_str

print("conf", get_configuration_str())

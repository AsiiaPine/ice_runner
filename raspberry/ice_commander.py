
import time
from typing import Any, Dict
import dronecan

from common.RPStates import RPStates
from common.IceRunnerConfiguration import IceRunnerConfiguration

# def dump_can_messages(node: dronecan.node.Node) -> None:
#     node_monitor = dronecan.app.node_monitor.NodeMonitor(node)
#     # callback for printing all messages in human-readable YAML format.
#     node.add_handler(None, msg_handler)

class ICEState:
    def __init__(self) -> None:
        self.is_exceeded = {"throttle": False, "temp": False, "rpm": False, "vin": False, "time": False}

        self.ice_state = RPStates.FAULT
        self.rpm: int = None
        self.throttle: int = None
        self.temp: int = None

        self.gas_throttle: int = None
        self.air_throttle: int = None

        self.current: float = None

        self.voltage_in: float = None
        self.voltage_out: float = None

        self.vibration: float = None

        self.engaged_time: float = None

    def update_with_resiprocating_status(self, msg) -> None:
        self.state.ice_state = msg.message.state
        self.state.rpm = msg.message.engine_speed_rpm
        self.state.throttle = msg.message.throttle_position_percent
        self.state.temp = msg.message.oil_temperature
        self.state.gas_throttle = msg.message.engine_load_percent
        self.state.air_throttle = msg.message.throttle_position_percent
        self.state.current = msg.message.intake_manifold_temperature
        self.state.voltage_in = msg.message.oil_pressure
        self.state.voltage_out = msg.message.oil_pressure

    def update_with_raw_imu(self, msg) -> None:
        self.state.vibration = msg.message.integration_interval

class DronecanCommander:
    def __init__(self, node: dronecan.node.Node, reporting_period: float = 0.1) -> None:
        self.node = node
        self.messages: Dict[str, Any] = {}
        self.state: ICEState = ICEState()
        self.reporting_period = reporting_period
        self.cmd = dronecan.uavcan.equipment.esc.RawCommand(cmd=[0]*7)
        self.node.add_handler(dronecan.uavcan.equipment.ice.reciprocating.Status, self.ice_reciprocating_status_handler)
        self.prev_broadcast_time = 0
        self.has_imu = False

    def raw_imu_handler(self, msg: dronecan.node.TransferEvent) -> None:
        self.status["vibration"] = msg.message.integration_interval
        self.messages['uavcan.equipment.ahrs.RawIMU'] = dronecan.to_yaml(msg.message)
        self.state.update_with_raw_imu(msg)
        self.has_imu = True
        self.dump_msg(msg)

    def ice_reciprocating_status_handler(self, msg: dronecan.node.TransferEvent) -> None:
        self.state.update_with_resiprocating_status(msg)
        self.messages['uavcan.equipment.ice.reciprocating.Status'] = dronecan.to_yaml(msg.message)
        self.dump_msg(msg)

    def dump_msg(self, msg: dronecan.node.TransferEvent) -> None:
        with open("test.txt", "a") as myfile:
            myfile.write(dronecan.to_yaml(msg))

    def spin(self) -> None:
        if time.time() - self.prev_broadcast_time > 0.1:
            self.prev_broadcast_time = time.time()
            print("Broadcasting")
            self.node.broadcast(self.cmd)
            print(self.messages)

class ICEFlags:
    def __init__(self) -> None:
        self.throttle_ex = False
        self.temp_ex = False
        self.rpm_ex = False
        self.vin_ex = False
        self.time_ex = False

class ICECommander:
    def __init__(self, node: dronecan.node.Node, reporting_period: float = 0.1, configuration: IceRunnerConfiguration = None) -> None:
        self.dronecan_commander = DronecanCommander(node, reporting_period)
        self.configuration = configuration
        self.flags = ICEFlags()
        self.start_time = 0

# fhdjkhfjksdhfjksdhfjkdshkjfs
    def check_conditions(self) -> int:
        state = self.dronecan_commander.state
        # check if conditions are exeeded
        if self.configuration.max_gas_throttle < state.throttle:
            self.flags.throttle_ex = True
            print("Throttle exeeded")
        if self.configuration.max_temperature < state.temp:
            self.flags.temp_ex = True
            print("Temperature exeeded")
        if self.configuration.rpm < state.rpm:
            self.flags.rpm_ex = True
            print("RPM exeeded")
        if self.configuration.min_vin_voltage > state.voltage_in:
            self.flags.vin_ex = True
            print("Vin exeeded")
        if self.start_time > 0 and self.configuration.time > time.time() - self.start_time:
            self.flags.time_ex = True
        if self.dronecan_commander.has_imu:
            if self.configuration.max_vibration < state.vibration:
                self.flags.vibration_ex = True
                print("Vibration exeeded")
        flags_attr = vars(self.flags)
        res = max([flags_attr[name] for name in flags_attr.keys() if flags_attr[name]])
        return res

    def spin(self) -> None:

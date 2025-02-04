import os
import sys
import time
import dronecan
import numpy as np
from raccoonlab_tools.dronecan.global_node import DronecanNode
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from common.ICEState import Health, Mode
from ice_sim.test_commander import ICE_AIR_CHANNEL, ICE_CMD_CHANNEL, ICENodeStatus

class Engine:
    def __init__(self):
        self.state = ICENodeStatus.STOPPED
        self.rpm = 0
        self.n_tries = 0
        self.prev_time = 0

    def update(self, cmd: int, air_cmd: int) -> None:
        if cmd == 0:
            self.state = ICENodeStatus.STOPPED
            self.rpm = 0
            return
        if self.n_tries > 2:
            self.rpm = cmd + np.sin((time.time() % 1000) * np.pi / 1000) * 500
            self.state = ICENodeStatus.RUNNING
            return

        if time.time() - self.prev_time > 2:
            if self.rpm == 0:
                self.state = ICENodeStatus.RUNNING
                self.rpm = 3000
                self.n_tries += 1
                self.prev_time = time.time()
                return

            self.prev_time = time.time()
            self.state = ICENodeStatus.WAITING
            self.rpm = 0
            return


class ICENODE:
    min_command: int = 2000
    status_timeout: float = 0.5
    command: int = 0
    air_cmd: int = 0
    gas_throttle: int = 0
    air_throttle: int = 0

    def __init__(self) -> None:
        self.node = DronecanNode(node_id= 101)
        self.dt = 0.05
        self.rpm = 0
        self.status = ICENodeStatus.STOPPED
        self.temp: float = 0
        self.int_temp: float = 0

        self.current: float = 40

        self.voltage_in: float = 40
        self.voltage_out: float = 5

        self.vibration: float = 0
        self.spark_ignition_time: float = 0
        self.engaged_time: float = 0
        self.node.node.mode = Mode.MODE_OPERATIONAL
        self.node.node.health = Health.HEALTH_OK
        self.prev_broadcast_time = 0
        self.engine = Engine()

    def create_ice_reciprocating_status(self) -> dronecan.uavcan.equipment.ice.reciprocating.Status:
        return dronecan.uavcan.equipment.ice.reciprocating.Status(
            ecu_index=0,
            state=self.engine.state.value,
            engine_speed_rpm=int(self.engine.rpm),
            atmospheric_pressure_kpa=int(self.engine.rpm),
            engine_load_percent=self.gas_throttle,
            throttle_position_percent=self.air_throttle,
            oil_temperature=self.temp,  
            coolant_temperature=self.int_temp,
            spark_plug_usage=0,
            estimated_consumed_fuel_volume_cm3=self.spark_ignition_time,
            intake_manifold_temperature=self.current,
            intake_manifold_pressure_kpa=5,
            oil_pressure=self.voltage_in)

    def send_ice_reciprocating_status(self, msg: dronecan.uavcan.equipment.ice.reciprocating.Status) -> None:
        self.node.publish(msg)

    def spin(self) -> None:
        self.node.node.spin(0)

        self.engine.update(cmd=self.command, air_cmd=self.air_cmd)
        if time.time() - self.prev_broadcast_time > self.status_timeout:
            self.prev_broadcast_time = time.time()
            self.node.publish(self.create_ice_reciprocating_status())
            self.node.publish(dronecan.uavcan.equipment.ice.FuelTankStatus(available_fuel_volume_percent=100))
            self.node.publish(dronecan.uavcan.equipment.ahrs.RawIMU(integration_interval=0))

def get_raw_command(res: dronecan.node.TransferEvent) -> int:
    if res is None:
        return 0
    cmd = res.message.cmd[ICE_CMD_CHANNEL]
    ICENODE.command = cmd
    ICENODE.gas_throttle = int(max(0, min(cmd, 6000)) / 100)

def get_air_cmd(res: dronecan.node.TransferEvent) -> int:
    if res is None:
        return 0
    for command in res.message.commands:
        if command.actuator_id == ICE_AIR_CHANNEL:
            cmd = command.command_value
            ICENODE.air_throttle = int(max(1000, min(cmd, 2000)) / 100)
            ICENODE.air_cmd = cmd


if __name__ == "__main__":
    node = ICENODE()
    node.node.node.add_handler(dronecan.uavcan.equipment.esc.RawCommand, get_raw_command)
    node.node.node.add_handler(dronecan.uavcan.equipment.actuator.ArrayCommand, get_air_cmd)
    while True:
        node.spin()

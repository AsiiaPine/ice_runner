
import asyncio
from enum import IntEnum
import time
from typing import Any, Dict
import dronecan
from common.RPStates import RPStates
from common.IceRunnerConfiguration import IceRunnerConfiguration
from mqtt_client import RaspberryMqttClient
from raccoonlab_tools.dronecan.utils import ParametersInterface
from raccoonlab_tools.dronecan.global_node import DronecanNode

import logging
import logging_configurator
logger = logging.getLogger(__name__)
# # GPIO setup
# import RPi.GPIO as GPIO # Import Raspberry Pi GPIO library
# GPIO.setwarnings(False) # Ignore warning for now
# GPIO.setmode(GPIO.BOARD) # Use physical pin numbering
# on_off_pin = 10
# start_stop_pin = 11

# GPIO.setup(on_off_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # On/Off button
# GPIO.setup(start_stop_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # Start/Stop button TODO: check pin

ICE_CMD_CHANNEL = 7 + 1

class Mode(IntEnum):
    MODE_OPERATIONAL      = 0         # Normal operating mode.
    MODE_INITIALIZATION   = 1         # Initialization is in progress; this mode is entered immediately after startup.
    MODE_MAINTENANCE      = 2         # E.g. calibration, the bootloader is running, etc.
    MODE_SOFTWARE_UPDATE  = 3         # New software/firmware is being loaded.
    MODE_OFFLINE          = 7         # The node is no longer available.

class Health(IntEnum):
    HEALTH_OK         = 0     # The node is functioning properly.
    HEALTH_WARNING    = 1     # A critical parameter went out of range or the node encountered a minor failure.
    HEALTH_ERROR      = 2     # The node encountered a major failure.
    HEALTH_CRITICAL   = 3     # The node suffered a fatal malfunction.

class RecipState(IntEnum):
    NOT_CONNECTED = -1
    STOPPED = 0
    RUNNING = 1
    WAITING = 2
    FAULT = 3

class ICEState:
    def __init__(self) -> None:
        self.ice_state: RecipState = RecipState.NOT_CONNECTED
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
        self.mode = Mode.MODE_OPERATIONAL
        self.health = Health.HEALTH_OK

    def update_with_resiprocating_status(self, msg) -> None:
        self.ice_state = RecipState(msg.message.state)
        self.rpm = msg.message.engine_speed_rpm
        self.throttle = msg.message.throttle_position_percent
        self.temp = msg.message.oil_temperature
        self.gas_throttle = msg.message.engine_load_percent
        self.air_throttle = msg.message.throttle_position_percent
        self.current = msg.message.intake_manifold_temperature
        self.voltage_in = msg.message.oil_pressure
        self.voltage_out = msg.message.oil_pressure

    def update_with_raw_imu(self, msg) -> None:
        self.vibration = msg.message.integration_interval

    def update_with_node_status(self, msg) -> None:
        self.mode = Mode(msg.mode) if msg.mode > self.mode else self.mode
        self.health = Health(msg.health) if msg.health > self.health else self.health
        if self.mode > Mode.MODE_SOFTWARE_UPDATE or self.health > Health.HEALTH_WARNING:
            self.ice_state = RecipState.FAULT

    def to_dict(self) -> Dict[str, Any]:
        vars_dict = vars(self)
        vars_dict["ice_state"] = RecipState(vars_dict["ice_state"]).value
        vars_dict["mode"] = Mode(vars_dict["mode"]).value
        vars_dict["health"] = Health(vars_dict["health"]).value
        return vars_dict

class DronecanCommander:
    node = None

    @classmethod
    def connect(cls) -> None:
        node: DronecanNode = DronecanNode()
        cls.node = node
        cls.messages: Dict[str, Any] = {}
        cls.state: ICEState = ICEState()
        cls.cmd = dronecan.uavcan.equipment.esc.RawCommand(cmd=[0]*ICE_CMD_CHANNEL)
        print("On sub", cls.node.sub_once(dronecan.uavcan.equipment.ice.reciprocating.Status))
        print("On sub", cls.node.sub_once(dronecan.uavcan.equipment.ahrs.RawIMU))
        cls.prev_broadcast_time = 0
        cls.param_interface = ParametersInterface(node.node, target_node_id=node.node.node_id)
        cls.has_imu = False
    
    def dump_msg(msg: dronecan.node.TransferEvent) -> None:
        with open("test.txt", "a") as myfile:
            myfile.write(dronecan.to_yaml(msg))

    @classmethod
    def spin(cls) -> None:
        cls.node.node.spin(1)
        # self.node
        if time.time() - cls.prev_broadcast_time > 0.1:
            print("Broadcasting")
            cls.prev_broadcast_time = time.time()
            cls.node.publish(cls.cmd)


def raw_imu_handler(msg: dronecan.node.TransferEvent) -> None:
    DronecanCommander.messages['uavcan.equipment.ahrs.RawIMU'] = dronecan.to_yaml(msg.message)
    DronecanCommander.state.update_with_raw_imu(msg)
    DronecanCommander.has_imu = True
    if DronecanCommander.state.engaged_time is None:
        DronecanCommander.param_interface._target_node_id = msg.message.source_node_id
        param = DronecanCommander.param_interface.get("stats.engaged_time")
        DronecanCommander.state.engaged_time = param.value
    print("Got IMU")
    DronecanCommander.dump_msg(msg)

def node_status_handler(msg: dronecan.node.TransferEvent) -> None:
    DronecanCommander.messages['uavcan.protocol.NodeStatus'] = dronecan.to_yaml(msg.message)
    DronecanCommander.state.update_with_node_status(msg)
    print("Got node status")

def ice_reciprocating_status_handler(msg: dronecan.node.TransferEvent) -> None:
    DronecanCommander.state.update_with_resiprocating_status(msg)
    DronecanCommander.messages['uavcan.equipment.ice.reciprocating.Status'] = dronecan.to_yaml(msg.message)
    DronecanCommander.dump_msg(msg)
    print("Got recip status")

def start_dronecan_handlers() -> None:
    DronecanCommander.node.node.add_handler(dronecan.uavcan.equipment.ice.reciprocating.Status, ice_reciprocating_status_handler)
    DronecanCommander.node.node.add_handler(dronecan.uavcan.equipment.ahrs.RawIMU, raw_imu_handler)
    DronecanCommander.node.node.add_handler(dronecan.uavcan.protocol.NodeStatus, node_status_handler)


class ICEFlags:
    def __init__(self) -> None:
        self.throttle_ex = False
        self.temp_ex = False
        self.rpm_ex = False
        self.vin_ex = False
        self.vibration_ex = False
        self.time_ex = False

class ICERunnerMode(IntEnum):
    SIMPLE = 0 # Юзер задает 30-50% тяги, и просто сразу же ее выставляем, без ПИД-регулятора. Без проверки оборотов, но с проверкой температуры.
    PID = 1 # Юзер задает обороты, и мы их поддерживаем ПИД-регулятором на стороне скрипта.
    RPM = 2 # Команда на 4500 оборотов (RPMCommand) без ПИД-регулятора на стороне скрипта - все на стороне платы.

class PIDController:
    def __init__(self, seeked_value: int) -> None:
        self.seeked_value = seeked_value
        self.kp = 0.1
        self.ki = 0.1
        self.kd = 0.1
        self.error = 0
        self.prev_time = 0
        self.drpm = 0
        self.prev_error = 0
        self.integral = 0

    def get_pid_command(self, val: int) -> int:
        self.prev_time = time.time()
        self.error = val - self.seeked_value
        self.drpm = (self.error - self.prev_error) / self.prev_time
        self.integral += self.ki*self.error*(time - self.prev_time)

        self.prev_error = self.error
        return self.seeked_value + self.kp*self.error + self.kd*self.drpm + self.ki * self.integral

class ICECommander:
    def __init__(self, reporting_period: float = 1, configuration: IceRunnerConfiguration = None) -> None:
        self.rp_state = RPStates.STOPPED
        self.reporting_period = reporting_period
        self.dronecan_commander = DronecanCommander
        self.dronecan_commander.connect()
        start_dronecan_handlers()
        self.configuration = configuration
        self.flags = ICEFlags()
        self.start_time = 0
        self.prev_waiting_state_time = 0
        self.mode = ICERunnerMode(configuration.mode)
        self.prev_report_time = 0
        if self.mode == ICERunnerMode.PID:
            self.pid_controller = PIDController(configuration.rpm)

    def check_conditions(self) -> int:
        state = self.dronecan_commander.state
        # check if conditions are exeeded
        if state.ice_state == RecipState.NOT_CONNECTED:
            self.rp_state = RPStates.NOT_CONNECTED
            return 0

        if self.start_time <= 0 or state.ice_state > RPStates.STARTING:
            self.flags.vin_ex = self.configuration.min_vin_voltage > state.voltage_in
            self.flags.temp_ex = self.configuration.max_temperature < state.temp
            eng_time_ex = False
            if state.engaged_time is not None:
              eng_time_ex = state.engaged_time > 40 * 60 * 60
              if eng_time_ex:
                  print(f"Engaged time {state.engaged_time} is exeeded")
            return sum([self.flags.vin_ex, self.flags.temp_ex,eng_time_ex])

        self.flags.throttle_ex = self.configuration.max_gas_throttle < state.throttle
        self.flags.temp_ex = self.configuration.max_temperature < state.temp
        self.flags.rpm_ex = self.configuration.rpm < state.rpm
        self.flags.time_ex = self.start_time > 0 and self.configuration.time > time.time() - self.start_time
        self.flags.vibration_ex = self.dronecan_commander.has_imu and self.configuration.max_vibration < state.vibration
        flags_attr = vars(self.flags)
        return sum([flags_attr[name] for name in flags_attr.keys() if flags_attr[name]])

    def set_command(self) -> None:
        if self.mode == ICERunnerMode.SIMPLE:
            self.dronecan_commander.cmd.cmd = self.configuration.rpm
        elif self.mode == ICERunnerMode.PID:
            self.dronecan_commander.cmd.cmd = [self.pid_controller.get_pid_command()] *ICE_CMD_CHANNEL
        elif self.mode == ICERunnerMode.RPM:
            self.dronecan_commander.cmd.cmd = [self.configuration.rpm] *ICE_CMD_CHANNEL

    async def spin(self) -> None:
        rp_state = self.rp_state 
        ice_state = self.dronecan_commander.state.ice_state
        RaspberryMqttClient.state = rp_state
        # self.check_buttons()
        self.check_mqtt_cmd()
        cond_exceeded = self.check_conditions()
        if ice_state == RecipState.STOPPED:
            self.start_time = 0
            self.rp_state = RPStates.STOPPED
            self.dronecan_commander.cmd.cmd = [0]*ICE_CMD_CHANNEL

        if cond_exceeded or self.start_time <= 0 or rp_state > RPStates.STARTING or ice_state > 2:
            self.start_time = 0
            self.dronecan_commander.cmd.cmd = [0]*ICE_CMD_CHANNEL
        else:
            if rp_state == RPStates.RUNNING:
                self.set_command()
            if rp_state == RPStates.STARTING:
                if time.time() - self.start_time > 4:
                    self.rp_state = RPStates.STOPPED
                    self.dronecan_commander.cmd.cmd = [0]*ICE_CMD_CHANNEL
                if self.dronecan_commander.state.ice_state == 1 and time.time() - self.prev_waiting_state_time > 2:
                    self.rp_state = RPStates.RUNNING
                    self.start_time = time.time()
        self.dronecan_commander.spin()
        await asyncio.sleep(0.01)

        if self.prev_report_time + self.reporting_period < time.time():
            state_dict = self.dronecan_commander.state.to_dict()
            state_dict["start_time"] = self.start_time
            state_dict["state"] = rp_state.value
            RaspberryMqttClient.get_client().publish("ice_runner/raspberry_pi/{rp_id}/state", rp_state.value)
            RaspberryMqttClient.status = state_dict
            RaspberryMqttClient.publish_messages(self.dronecan_commander.messages)
            RaspberryMqttClient.publish_stats(state_dict)
            self.prev_report_time = time.time()


    async def run(self) -> None:
        while True:
            await self.spin()

    # def check_buttons(self):
    #     start_switch = GPIO.input(start_stop_pin)
    #     power_switch = GPIO.input(on_off_pin)
    #     if not power_switch:
    #         self.rp_state = RPStates.STOPPING
    #     if start_switch:
    #         self.rp_state = RPStates.STARTING if self.rp_state > RPStates.STARTING else self.rp_state
    #     else:
    #         self.rp_state = RPStates.STOPPING

    def check_mqtt_cmd(self):
        if RaspberryMqttClient.to_stop:
            self.rp_state = RPStates.STOPPING
            RaspberryMqttClient.to_stop = 0
        if RaspberryMqttClient.to_run:
            self.rp_state = RPStates.STARTING if self.rp_state > RPStates.STARTING else self.rp_state
            RaspberryMqttClient.to_run = 0

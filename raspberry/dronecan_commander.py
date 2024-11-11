import logging
import os
import sys
import time
from typing import Any, Dict, List

from mqtt_client import RaspberryMqttClient
from raccoonlab_tools.dronecan.global_node import DronecanNode
from raccoonlab_tools.dronecan.utils import NodeFinder

sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '../dronecan_communication')))
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from common.IceRunnerConfiguration import IceRunnerConfiguration
from dronecan_communication.nodes_communicator import NodeType
import dronecan_communication.DronecanMessages as messages
logger = logging.getLogger(__name__)

CMDChannel = 7

RAWCmdStep = 100
RPMCmdStep = 100

RPMMax = 6000
RPMMin = 3000

RAWMax = 6000
RAWMin = 3000

class DronecanCommander:
    stop_message = messages.ESCRPMCommand(command=[0]*CMDChannel)
    current_rpm_command = messages.ESCRPMCommand(command=[0]*CMDChannel)
    current_raw_command = messages.ESCRawCommand(command=[0]*CMDChannel)
    configuration: IceRunnerConfiguration
    node: DronecanNode
    finder: NodeFinder
    last_report_time = 0
    is_started = False
    state = Dict[str, Any]
    # to_run: bool = 0
    rx_mes_types: list[messages.Message] = [messages.NodeStatus,
                    messages.ICEReciprocatingStatus,
                    messages.FuelTankStatus,
                    messages.ActuatorStatus,
                    messages.ImuVibrations,
                    messages.ESCStatus]

    @classmethod
    def connect(cls, logging_interval_s: int = 10) -> None:
        cls.node = DronecanNode()
        cls.finder = NodeFinder(cls.node.node)
        cls.logging_interval_s = logging_interval_s
        cls.last_logging_time = 0
        cls.messages: Dict[str, messages.Message] = {}
        cls.state = Dict[str, Any] = {}
        cls.start_time = -1

    @classmethod
    def set_parameters(cls, parameters: Dict[str, Any]) -> None:
        cls.communicator.set_parameters_to_nodes(parameters, NodeType.ICE)

    @classmethod
    def start(cls) -> None:
        print("Start")
        cls.start_time = time.time()

        cls.set_raw_command(RAWMin)
        cls.set_rpm(RPMMin)
        cls.node.publish(cls.current_rpm_command.to_dronecan())
        cls.node.publish(cls.current_raw_command.to_dronecan())

    @classmethod
    def stop(cls) -> None:
        print("Stop")
        cls.node.publish(cls.stop_message.to_dronecan())

    @classmethod
    def check_conditions(cls) -> int:
        # print(cls.states)
        throttle_ex = False
        temp_ex = False
        rpm_ex = False
        vin_ex = False

        if messages.ICEReciprocatingStatus.name in cls.messages.keys():
            recip_status: messages.ICEReciprocatingStatus = cls.messages[messages.ICEReciprocatingStatus.name]
            # check if conditions are exeeded
            throttle_ex = cls.configuration.max_gas_throttle < recip_status.engine_load_percent
            temp_ex = cls.configuration.max_temperature < recip_status.oil_temperature

            rpm_ex = cls.configuration.rpm < recip_status.engine_speed_rpm
            vin_ex = cls.configuration.min_vin_voltage < recip_status.oil_pressure
        else:
            print("No ICE status")
            return -1
        #  TODO: add fuel volume check
        # cls.configuration.min_fuel_volume
        time_ex = False
        if cls.start_time > 0:
            time_ex = cls.configuration.time > time.time() - cls.start_time

        vibration_ex = False
        if messages.ImuVibrations.name in cls.messages.keys():
            imu_status: messages.ImuVibrations = cls.messages[messages.ImuVibrations.name]
            vibration_ex = cls.configuration.max_vibration < imu_status.vibration

        # Some of the conditions are exeeded
        if throttle_ex or temp_ex or vibration_ex or time_ex or rpm_ex or vin_ex:
            conditions = [throttle_ex, temp_ex, vibration_ex, time_ex, rpm_ex, vin_ex]
            for i in range(len(conditions)):
                if conditions[i]:
                    print(f"Real temperature: {recip_status.oil_temperature}, configured temperature: {cls.configuration.max_temperature}")
                    print(f"Condition {i} is exeeded")
            return -1

        rpm_smaller = recip_status.engine_speed_rpm < cls.configuration.rpm

        # RPM is smaller than configured
        if rpm_smaller:
            return 1

        # All is ok
        return 0

    @classmethod
    def report(cls) -> None:
        if time.time() - cls.last_report_time > cls.logging_interval_s:
            cls.last_report_time = time.time()
            logger.info(f"Ice nodes statuses:\n\t{[ice_message.to_dict() for ice_message in cls.messages.values()]}")
            RaspberryMqttClient.publish_state(cls.messages)


    @classmethod
    def run(cls) -> None:
        if RaspberryMqttClient.to_stop:
            cls.stop()
            RaspberryMqttClient.to_stop = 0
        if RaspberryMqttClient.to_run:
            if cls.is_started:
                cls.stop()
            cls.start()
            RaspberryMqttClient.to_run = 0
        to_start = True
        if to_start:
            cls.start()
            cls.is_started = True

        while cls.is_started:
            cls.get_states()
            res = cls.check_conditions()
            if res == -1:
                cls.reduce_setpoint()
            elif res == 1:
                cls.increase_setpoint()
            if res == 0:
                print("No conditions are exeeded")
            if res == -1:
                print("Conditions are exeeded")
            if res == 1:
                print("RPM ", cls.messages[messages.ICEReciprocatingStatus.name].engine_speed_rpm, " is slower then", cls.configuration.rpm)
            cls.node.publish(cls.current_rpm_command.to_dronecan())
            cls.node.publish(cls.current_raw_command.to_dronecan())
            cls.report()
            # await asyncio.sleep(0.1)
        cls.run()

    @classmethod
    def set_setpoint(cls, rpm: int) -> None:
        cls.current_raw_command = messages.ESCRawCommand(command=[rpm]*CMDChannel)
        cls.current_rpm_command = messages.ESCRPMCommand(command=[rpm]*CMDChannel)

    @classmethod
    def reduce_setpoint(cls) -> None:
        curr_prm_cmd = cls.current_rpm_command.command[0]
        curr_raw_cmd = cls.current_raw_command.command[0]
        if cls.current_rpm_command.command[0] > RPMMin:
            curr_prm_cmd -= RPMCmdStep
        if cls.current_raw_command.command[0] > RAWMin:
            curr_raw_cmd -= RAWCmdStep

        cls.set_raw_command(curr_raw_cmd)
        cls.set_rpm(curr_prm_cmd)

    @classmethod
    def increase_setpoint(cls) -> None:
        curr_prm_cmd = cls.current_rpm_command.command[0]
        curr_raw_cmd = cls.current_raw_command.command[0]
        if cls.current_rpm_command.command[0] < RPMMax:
            curr_prm_cmd += RPMCmdStep

        if cls.current_raw_command.command[0] < RAWMax:
            curr_raw_cmd += RAWCmdStep

        cls.set_raw_command(curr_raw_cmd)
        cls.set_rpm(curr_prm_cmd)

    @classmethod
    def set_raw_command(cls, value: int) -> None:
        cls.current_raw_command = messages.ESCRawCommand(command=[value] * CMDChannel)

    @classmethod
    def set_rpm(cls, value: int) -> None:
        cls.current_rpm_command = messages.ESCRawCommand(command=[value]*CMDChannel)

    @classmethod
    def get_states(cls):
        for mess_type in cls.rx_mes_types:
            message = cls.node.sub_once(mess_type.dronecan_type)
            if message is None:
                continue
            cls.messages[mess_type.name] = mess_type.from_message(message.message)

        cls.state["rpm"] = cls.messages[messages.ICEReciprocatingStatus.name].engine_speed_rpm
        cls.state["throttle"] = cls.messages[messages.ICEReciprocatingStatus.name].engine_load_percent
        cls.state["temp"] = cls.messages[messages.ICEReciprocatingStatus.name].oil_temperature
        cls.state["voltage"] = cls.messages[messages.RawImu.name].rate_gyro_latest[0]
        cls.state["current"] = cls.messages[messages.RawImu.name].rate_gyro_latest[1]
        cls.state["fuel_volume"] = cls.messages[messages.FuelTankStatus.name].fuel_consumption_rate_cm3pm
        if messages.ImuVibrations.name in cls.messages.keys():
            cls.state["vibration"] = cls.messages[messages.ImuVibrations.name].vibration
        # cls.state["time"] = time.time()
        cls.state["start_time"] = cls.start_time
        cls.state["run_time"] = time.time() - cls.start_time
        cls.state["state"] = cls.messages[messages.ICEReciprocatingStatus.name].state

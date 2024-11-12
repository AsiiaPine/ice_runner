import logging
import os
import sys
import time
from typing import Any, Dict, List

from mqtt_client import RaspberryMqttClient
from raccoonlab_tools.dronecan.global_node import DronecanNode
from raccoonlab_tools.dronecan.utils import NodeFinder, ParametersInterface
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '../dronecan_communication')))
sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from common.IceRunnerConfiguration import IceRunnerConfiguration
from dronecan_communication.nodes_communicator import NodeType
import dronecan_communication.DronecanMessages as messages

# # GPIO setup
# import RPi.GPIO as GPIO # Import Raspberry Pi GPIO library
# GPIO.setwarnings(False) # Ignore warning for now
# GPIO.setmode(GPIO.BOARD) # Use physical pin numbering
# GPIO.setup(10, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # Set pin 10 to be an input pin and set initial value to be pulled low (off)

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
    status: Dict[str, Any] = {}
    rx_mes_types: list[messages.Message] = [messages.NodeStatus,
                    messages.ICEReciprocatingStatus,
                    messages.FuelTankStatus,
                    messages.ActuatorStatus,
                    messages.ImuVibrations,
                    messages.ESCStatus]

    @classmethod
    def check_engaged_time(cls) -> None:
        nodes = cls.finder.find_online_nodes(timeout_sec=0.1)
        if len(cls.finder.node.node.nodes) < 1:
            print("No nodes found")
            return
        for node in nodes:
            params_interface = ParametersInterface(node.node, target_node_id=node.node_id)
            params = params_interface.get_all()
            if "stats.engaged_time" in params.keys():
                cls.status["engaged_time"] = params["stats.engaged_time"]

    @classmethod
    def connect(cls, logging_interval_s: int = 10) -> None:
        cls.node = DronecanNode()
        cls.finder = NodeFinder(cls.node.node)
        cls.logging_interval_s = logging_interval_s
        cls.last_logging_time = 0
        cls.messages: Dict[str, messages.Message] = {}
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
    def prestart_check(cls) -> bool:
        if messages.ICEReciprocatingStatus.name in cls.messages.keys():
            recip_status: messages.ICEReciprocatingStatus = cls.messages[messages.ICEReciprocatingStatus.name]
            if cls.configuration.min_vin_voltage > recip_status.oil_pressure:
                # TODO: start beep, not enough battery voltage
                return False
            return True
        else:
            # TODO: start beep, no ICE is connected
            return False

    @classmethod
    def check_conditions(cls) -> int:
        state = {"throttle": False, "temp": False, "rpm": False, "vin": False, "time": False}
        cls.configuration = RaspberryMqttClient.configuration
        if messages.ICEReciprocatingStatus.name in cls.messages.keys():
            recip_status: messages.ICEReciprocatingStatus = cls.messages[messages.ICEReciprocatingStatus.name]
            # check if conditions are exeeded
            state["throttle"] = cls.configuration.max_gas_throttle < recip_status.engine_load_percent
            state["temp"] = cls.configuration.max_temperature < recip_status.oil_temperature

            state["rpm"] = cls.configuration.rpm < recip_status.engine_speed_rpm
            state["vin"] = cls.configuration.min_vin_voltage > recip_status.oil_pressure
        else:
            print("No ICE status")
            cls.stop()
            return -1
        #  TODO: add fuel volume check
        # cls.configuration.min_fuel_volume
        state["time"] = False
        if cls.start_time > 0:
            state["time"] = cls.configuration.time > time.time() - cls.start_time

        state["vibration"] = False
        if messages.ImuVibrations.name in cls.messages.keys():
            imu_status: messages.ImuVibrations = cls.messages[messages.ImuVibrations.name]
            state["vibration"] = cls.configuration.max_vibration < imu_status.vibration

        # Some of the conditions are exeeded
        for confition, exeeded in state.items():
            if exeeded:
                print(f"Condition {confition} is exeeded")
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
            RaspberryMqttClient.publish_messages(cls.messages)
            RaspberryMqttClient.publish_stats(cls.status)
            RaspberryMqttClient.client.publish(f"ice_runner/server/bot_commander/rp_states/{RaspberryMqttClient.rp_id}/configuration", str(RaspberryMqttClient.configuration.to_dict()))

    @classmethod
    def run(cls) -> None:
        # if GPIO.input(10) == GPIO.HIGH:
        #     print("Button was pushed!")
        #     if cls.is_started:
        #         cls.stop()
        #     else:
        #         cls.start()

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
            try:   
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
                RaspberryMqttClient.status = cls.status
                # await asyncio.sleep(0.1)
            except Exception as e:
                print(e)
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

        if messages.ICEReciprocatingStatus.name in cls.messages.keys():
            cls.status["rpm"] = cls.messages[messages.ICEReciprocatingStatus.name].engine_speed_rpm
            cls.status["gas_throttle"] = cls.messages[messages.ICEReciprocatingStatus.name].engine_load_percent
            cls.status["air_throttle"] = cls.messages[messages.ICEReciprocatingStatus.name].throttle_position_percent
            cls.status["temp"] = cls.messages[messages.ICEReciprocatingStatus.name].oil_temperature
            cls.status["voltage"] = cls.messages[messages.ICEReciprocatingStatus.name].oil_pressure
            cls.status["current"] = cls.messages[messages.ICEReciprocatingStatus.name].intake_manifold_temperature
            cls.status["state"] = cls.messages[messages.ICEReciprocatingStatus.name].state.value
        else:
            print("No ICE status")
        if messages.FuelTankStatus.name in cls.messages.keys():
            cls.status["fuel_volume"] = cls.messages[messages.FuelTankStatus.name].fuel_consumption_rate_cm3pm
        if messages.ImuVibrations.name in cls.messages.keys():
            cls.status["vibration"] = cls.messages[messages.ImuVibrations.name].vibration
        # cls.state["time"] = time.time()
        if "stats.engaged_time" in cls.status.keys():
            cls.status["engaged_time"]+= time.time() - cls.start_time if cls.start_time > 0 else 0
        cls.status["start_time"] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(cls.start_time))

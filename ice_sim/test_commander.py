#!/usr/bin/env python3
# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Dmitry Ponomarev.
# Author: Dmitry Ponomarev <ponomarevda96@gmail.com>
import os
import sys
import secrets
import subprocess
import pytest
import dronecan
import time
from enum import IntEnum
from paho.mqtt.client import MQTTv311, Client

from raccoonlab_tools.common.protocol_parser import CanProtocolParser, Protocol
from raccoonlab_tools.dronecan.global_node import DronecanNode
from raccoonlab_tools.dronecan.utils import (
    Parameter,
    ParametersInterface,
    NodeCommander,
)

ICE_CMD_CHANNEL = 7

class ICENodeStatus(IntEnum):
    STOPPED = 0
    RUNNING = 1
    WAITING = 2
    FAULT = 3

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

class ICENODE:
    min_command: int = 2000
    status_timeout: float = 0.1

    def __init__(self) -> None:
        self.node = DronecanNode()
        self.command = dronecan.uavcan.equipment.esc.RawCommand(cmd=[0]*(ICE_CMD_CHANNEL + 1))
        self.rpm = 0
        self.status = ICENodeStatus.STOPPED
        self.temp: int = 0

        self.gas_throttle: int = 0
        self.air_throttle: int = 0

        self.current: float = None

        self.voltage_in: float = 40
        self.voltage_out: float = 5

        self.vibration: float = 0
        self.spark_ignition_time: float = 0
        self.engaged_time: float = 0
        print("self.mode = Mode.MODE_OPERATIONAL", type(self.mode))
        self.mode = Mode.MODE_OPERATIONAL
        print("self.mode = Mode.MODE_OPERATIONAL ", type(self.mode))
        self.health = Health.HEALTH_OK

    def random_rpm_change(self) -> int:
        return secrets.randbelow(1000) 

    def create_ice_reciprocating_status(self) -> dronecan.uavcan.equipment.ice.reciprocating.Status:
        return dronecan.uavcan.equipment.ice.reciprocating.Status(
            state=self.status.value,
            flags=0,
            engine_load_percent=self.gas_throttle,
            engine_speed_rpm=self.rpm,
            spark_dwell_time_ms=0,
            atmospheric_pressure_kpa=self.rpm,
            intake_manifold_pressure_kpa=5,
            intake_manifold_temperature=self.current,
            coolant_temperature=0,
            oil_pressure=self.voltage_in,
            oil_temperature=self.temp,
            fuel_pressure=0,
            fuel_consumption_rate_cm3pm=0,
            estimated_consumed_fuel_volume_cm3=self.spark_ignition_time,
            throttle_position_percent=self.air_throttle,
            ecu_index=0,
            spark_plug_usage=0,
            cylinder_status=[]
        )

    def send_ice_reciprocating_status(self, msg: dronecan.uavcan.equipment.ice.reciprocating.Status) -> None:
        self.node.publish(msg)

    def get_raw_command(self, timeout_sec=0.03):
        res = self.node.sub_once(
            dronecan.uavcan.equipment.esc.RawCommand, timeout_sec
        )
        return res.message.cmd[ICE_CMD_CHANNEL]

@pytest.mark.dependency()
def test_node_existance():
    """
    This test is required just for optimization purposes.
    Let's skip all tests if we don't have an online Cyphal node.
    """
    assert CanProtocolParser.verify_protocol(white_list=[Protocol.DRONECAN])

# def compare_beeper_command_values(
#     first: dronecan.uavcan.equipment.indication.BeepCommand,
#     second: dronecan.uavcan.equipment.indication.BeepCommand,
# ):
#     return first.duration == second.duration and first.frequency == second.frequency


def test_receive_get_raw_command():
    node = ICENODE()
    node.send_ice_reciprocating_status(node.create_ice_reciprocating_status())
    assert node.get_raw_command() == 0

def test_get_zero_cmd():
    node = ICENODE()
    node.status = ICENodeStatus.RUNNING
    assert node.get_raw_command() == 0

def test_mqtt_cmd():
    client: Client = Client(client_id="raspberry_0", clean_session=True, userdata=None, protocol=MQTTv311)

    node = ICENODE()

# 1
@pytest.mark.dependency()
def test_transport():
    """
    This test is required just for optimization purposes.
    Let's skip all tests if we don't have an online Cyphal node.
    """
    assert CanProtocolParser.verify_protocol(white_list=[Protocol.DRONECAN])


# 2
@pytest.mark.dependency()
def test_beeper_command_feedback():
    pmu = PMUNode()
    config = [Parameter(name=PARAM_BUZZER_VERBOSE, value=1)]
    pmu.configure(config)
    time.sleep(5)
    recv_sound = pmu.recv_sound()
    assert recv_sound is not None


@pytest.mark.dependency(depends=["test_transport", "test_beeper_command_feedback"])
class TestGateOk:
    """
    The test class with maximum gate_threshold value, 
    so the node will always listen to the BeepCommands
    """

    config = [
        Parameter(name=PARAM_BATTERY_ID, value=0),
        Parameter(name=PARAM_BATTERY_MODEL_INSTANCE_ID, value=0),
        Parameter(name=PARAM_BUZZER_ERROR_MELODY, value=127),
        Parameter(name=PARAM_BUZZER_FREQUENCY, value=ParamLightsType.SOLID),
        Parameter(name=PARAM_GATE_THRESHOLD, value=4095),
        Parameter(name=PARAM_BUZZER_VERBOSE, value=1),
    ]
    pmu = PMUNode()
    randomizer = secrets.SystemRandom()
    @staticmethod
    def configure_node():
        TestGateOk.pmu.configure(TestGateOk.config)
        time.sleep(5)

    @staticmethod
    def test_healthy_node_sound_after_restart():
        pmu = TestGateOk.pmu
        TestGateOk.configure_node()
        recv = pmu.recv_sound()
        expected_duration = 0
        assert recv is not None
        assert compare_beeper_command_duration_values(
            recv, expected_duration=expected_duration
        )

    @pytest.mark.dependency(depends=["test_healthy_node_sound_after_restart"])
    @staticmethod
    def test_send_random_sound():
        pmu = TestGateOk.pmu

        frequency = TestGateOk.randomizer.randrange(start=PMUNode.min_frequency, stop=1000, step=10)
        duration = 2
        msg = make_beeper_cmd_from_values(frequency=frequency, duration=duration)
        pmu.send_beeper_command(msg)
        recv = None

        assert pmu.check_beep_cmd_response(msg)

    @pytest.mark.dependency()
    @staticmethod
    def test_silence_after_command_ttl():
        pmu = TestGateOk.pmu
        frequency = TestGateOk.randomizer.randrange(start=PMUNode.min_frequency, stop=1000, step=10)
        duration = TestGateOk.randomizer.uniform(0.1, 1)

        msg = make_beeper_cmd_from_values(frequency=frequency, duration=duration)
        pmu.send_beeper_command(msg)

        time.sleep(duration)
        recv = None
        for _ in range(20):
            recv = pmu.recv_sound()
        assert recv is not None
        assert compare_beeper_command_duration_values(recv, expected_duration=0)

    @staticmethod
    def test_beep_command_subscription():
        pmu = TestGateOk.pmu

        expected_counter = 0
        unexpected_counter = 0

        number_of_notes = 20
        
        for _ in range(number_of_notes):
            frequency = TestGateOk.randomizer.randrange(start=PMUNode.min_frequency, stop=1000, step=10)
            duration = TestGateOk.randomizer.uniform(0.1, 1)

            msg = make_beeper_cmd_from_values(frequency=frequency, duration=duration)
            pmu.send_beeper_command(msg)

            if pmu.check_beep_cmd_response(msg):
                expected_counter += 1
            else:
                unexpected_counter += 1

        total_counter = expected_counter + unexpected_counter

        hint = (
            f"{TestGateOk.__doc__}. "
            f"Expected: {expected_counter}/{total_counter}. "
            f"Unexpected: {unexpected_counter}/{total_counter}. "
        )

        assert unexpected_counter == 0, f"{hint}"
        assert expected_counter > 0, f"{hint}"

    @staticmethod
    def test_beep_command_subscription_with_duration():
        pmu = TestGateOk.pmu

        expected_counter = 0
        unexpected_counter = 0

        duration_comply_failure_counter = 0
        number_of_notes = 20
        for _ in range(number_of_notes):
            frequency = TestGateOk.randomizer.randrange(start=PMUNode.min_frequency, stop=1000, step=10)
            duration = TestGateOk.randomizer.uniform(0.1, 1)

            msg = make_beeper_cmd_from_values(frequency=frequency, duration=duration)
            pmu.send_beeper_command(msg)
            start_time = time.time()
            timeout_sec = 0.05
            while time.time() - start_time < duration - timeout_sec:
                if pmu.check_beep_cmd_response(msg):
                    expected_counter += 1
                else:
                    unexpected_counter += 1

            for _ in range(15):
                recv = pmu.recv_sound()
            assert recv is not None
            if not compare_beeper_command_duration_values(recv, expected_duration=0):
                duration_comply_failure_counter += 1

        total_counter = expected_counter + unexpected_counter

        hint = (
            f"{TestGateOk.__doc__}. "
            f"Expected: {expected_counter}/{total_counter}. "
            f"Unexpected: {unexpected_counter}/{total_counter}. "
            f"Duration comply failures: {duration_comply_failure_counter}/{number_of_notes}. "
        )

        assert unexpected_counter == 0, f"{hint}"
        assert expected_counter > 0, f"{hint}"
        assert duration_comply_failure_counter == 0, f"{hint}"


def main():
    cmd = ["pytest", os.path.abspath(__file__)]
    cmd += ["--tb=no"]  # No traceback at all
    cmd += ["-v"]  # Increase verbosity
    cmd += ["-W", "ignore::DeprecationWarning"]  # Ignore specific warnings
    cmd += sys.argv[1:]  # Forward optional user flags
    print(len(cmd))
    print(cmd)
    sys.exit(subprocess.call(cmd))


if __name__ == "__main__":
    main()

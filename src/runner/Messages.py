from enum import Enum
from typing import List
import dronecan
from dataclasses import dataclass

@dataclass
class Message:
    name = 'Message'
    dronecan_type = None
    source_id: int
    timestamp: int

@dataclass
class NodeStatus:
    """ Abstract node status information. All UAVCAN nodes are required to publish this message periodically."""
    name = 'NodeStatus'
    dronecan_type = dronecan.uavcan.protocol.NodeStatus

    class Mode(Enum):
        MODE_OPERATIONAL      = 0         # Normal operating mode.
        MODE_INITIALIZATION   = 1         # Initialization is in progress; this mode is entered immediately after startup.
        MODE_MAINTENANCE      = 2         # E.g. calibration, the bootloader is running, etc.
        MODE_SOFTWARE_UPDATE  = 3         # New software/firmware is being loaded.
        MODE_OFFLINE          = 7         # The node is no longer available.
    
    class Health(Enum):
        HEALTH_OK         = 0     # The node is functioning properly.
        HEALTH_WARNING    = 1     # A critical parameter went out of range or the node encountered a minor failure.
        HEALTH_ERROR      = 2     # The node encountered a major failure.
        HEALTH_CRITICAL   = 3     # The node suffered a fatal malfunction.

    uptime_sec: int
    health: Health
    mode: Mode

    sub_mode: int = 0 # Not used currently, keep zero when publishing, ignore when receiving.
    
    vendor_specific_status_code: int = 0 # Optional, vendor-specific node status code, e.g. a fault code or a status bitmask.
    def from_message(self, msg: dronecan.uavcan.protocol.NodeStatus):
        self.uptime_sec = msg.uptime_sec
        self.health = NodeStatus.Health(msg.health)
        self.mode = NodeStatus.Mode(msg.mode)
        self.sub_mode = msg.sub_mode
        self.vendor_specific_status_code = msg.vendor_specific_status_code
        return self

@dataclass
class CylinderStatus:
    # Cylinder state information.
    # This is a nested data type.

    # Cylinder ignition timing. Units: angular degrees of the crankshaft.
    ignition_timing_deg: float|None

    injection_time_ms: float|None # Fuel injection time. Units: millisecond.
    cylinder_head_temperature: float|None # Cylinder head temperature (CHT).  Units: kelvin.

    # Exhaust gas temperature (EGT). Set this field to the same value for all cylinders if there is a single shared EGT sensor.  Units: kelvin.
    exhaust_gas_temperature: float|None

    # Estimated lambda coefficient. This parameter is mostly useful for monitoring and tuning purposes. Unit: dimensionless ratio
    lambda_coefficient: float|None
    def from_message(self, msg):
        self.ignition_timing_deg = msg.ignition_timing_deg
        self.injection_time_ms = msg.injection_time_ms
        self.cylinder_head_temperature = msg.cylinder_head_temperature
        self.exhaust_gas_temperature = msg.exhaust_gas_temperature
        self.lambda_coefficient = msg.lambda_coefficient
        return self

@dataclass
class ICEReciprocating(Message):
    name = 'ICEReciprocating'
    dronecan_type = dronecan.uavcan.equipment.ice.reciprocating

    class State(Enum):
        STATE_STOPPED   = 0, # The engine is not running. This is the default state.
        STATE_STARTING  = 1, # The engine is starting. This is a transient state.
        STATE_RUNNING   = 2, # The engine is running normally.
        STATE_FAULT     = 3  # The engine can no longer function.

    class Flags(Enum):
        FLAG_GENERAL_ERROR = 1, # General error. This flag is required, and it can be used to indicate an error condition that does not fit any of the other flags.
        FLAG_CRANKSHAFT_SENSOR_ERROR_SUPPORTED = 2,
        FLAG_CRANKSHAFT_SENSOR_ERROR = 3,
        FLAG_TEMPERATURE_SUPPORTED = 8,
        FLAG_TEMPERATURE_BELOW_NOMINAL = 16,
        FLAG_TEMPERATURE_ABOVE_NOMINAL = 32,
        FLAG_TEMPERATURE_OVERHEATING = 64,
        FLAG_TEMPERATURE_EGT_ABOVE_NOMINAL = 128,
        FLAG_FUEL_PRESSURE_SUPPORTED = 256,
        FLAG_FUEL_PRESSURE_BELOW_NOMINAL = 512,
        FLAG_FUEL_PRESSURE_ABOVE_NOMINAL = 1024,
        FLAG_DETONATION_SUPPORTED = 2048,
        FLAG_DETONATION_OBSERVED = 4096,
        FLAG_MISFIRE_SUPPORTED = 8192,
        FLAG_MISFIRE_OBSERVED = 16384,
        FLAG_OIL_PRESSURE_SUPPORTED = 32768,
        FLAG_OIL_PRESSURE_BELOW_NOMINAL = 65536,
        FLAG_OIL_PRESSURE_ABOVE_NOMINAL = 131072,
        FLAG_DEBRIS_SUPPORTED = 262144,
        FLAG_DEBRIS_DETECTED = 524288,
    
    class SparkPlugUsage(Enum):
        SPARK_PLUG_SINGLE         = 0,
        SPARK_PLUG_FIRST_ACTIVE   = 1,
        SPARK_PLUG_SECOND_ACTIVE  = 2,
        SPARK_PLUG_BOTH_ACTIVE    = 3
    state: State
    flags: int
    engine_load_percent: int
    engine_speed_rpm: int

    spark_dwell_time_ms: float|None
    atmospheric_pressure_kpa: float|None # Atmospheric (barometric) pressure. Unit: kilopascal.
    intake_manifold_pressure_kpa: float|None # Engine intake manifold pressure. Unit: kilopascal.
    intake_manifold_temperature: float|None # Engine intake manifold temperature. Unit: kelvin.
    coolant_temperature: float|None # Engine coolant temperature. Unit: kelvin.
    oil_pressure: float|None # Oil pressure. Unit: kilopascal.
    oil_temperature: float|None # Oil temperature. Unit: kelvin.
    fuel_pressure: float|None # Fuel pressure. Unit: kilopascal.

    # Instant fuel consumption estimate. The estimated value should be low-pass filtered in order to prevent aliasing effects. Unit: (centimeter^3)/minute.
    fuel_consumption_rate_cm3pm: float|None

    # Estimate of the consumed fuel since the start of the engine.
    # This variable MUST be reset when the engine is stopped. Unit: centimeter^3.
    estimated_consumed_fuel_volume_cm3: int
    throttle_position_percent: int # Throttle position. Unit: percent.
    ecu_index: int # The index of the publishing ECU.

    spark_plug_usage: SparkPlugUsage # Spark plug activity report. Can be used during pre-flight tests of the spark subsystem.
    cylinder_status : CylinderStatus # Per-cylinder status information.

    def from_message(self, msg: dronecan.uavcan.equipment.ice.reciprocating):
        self.state = ICEReciprocating.State(msg.state)
        self.flags = msg.flags
        self.engine_load_percent = msg.engine_load_percent
        self.engine_speed_rpm = msg.engine_speed_rpm
        self.spark_dwell_time_ms = msg.spark_dwell_time_ms
        self.atmospheric_pressure_kpa = msg.atmospheric_pressure_kpa
        self.intake_manifold_pressure_kpa = msg.intake_manifold_pressure_kpa
        self.intake_manifold_temperature = msg.intake_manifold_temperature
        self.coolant_temperature = msg.coolant_temperature
        self.oil_pressure = msg.oil_pressure
        self.oil_temperature = msg.oil_temperature
        self.fuel_pressure = msg.fuel_pressure
        self.fuel_consumption_rate_cm3pm = msg.fuel_consumption_rate_cm3pm
        self.estimated_consumed_fuel_volume_cm3 = msg.estimated_consumed_fuel_volume_cm3
        self.throttle_position_percent = msg.throttle_position_percent
        self.ecu_index = msg.ecu_index
        self.spark_plug_usage = ICEReciprocating.SparkPlugUsage(msg.spark_plug_usage)
        self.cylinder_status = ICEReciprocating.CylinderStatus()
        for i in len(msg.cylinder_status):
            self.cylinder_status[i] = ICEReciprocating.CylinderStatus()
            self.cylinder_status[i].from_message(msg.cylinder_status[i])
        return self

@dataclass
class FuelTankStatus(Message):
    name = 'FuelTankStatus'
    dronecan_type = dronecan.uavcan.equipment.ice.FuelTankStatus
    # Generic fuel tank status message.

    available_fuel_volume_percent: int     # Unit: percent, from 0% to 100%
    available_fuel_volume_cm3: float       # Unit: centimeter^3
    fuel_consumption_rate_cm3pm: float
    fuel_temperature: float|None
    fuel_tank_id: int
    def from_message(self, msg: dronecan.uavcan.equipment.ice.FuelTankStatus):
        self.available_fuel_volume_percent = msg.available_fuel_volume_percent
        self.available_fuel_volume_cm3 = msg.available_fuel_volume_cm3
        self.fuel_consumption_rate_cm3pm = msg.fuel_consumption_rate_cm3pm
        self.fuel_temperature = msg.fuel_temperature
        self.fuel_tank_id = msg.fuel_tank_id
        return self

@dataclass
class ESCStatus(Message):
    name = 'ESCStatus'
    dronecan_type = dronecan.uavcan.equipment.esc.Status
    # Generic ESC status message.

    error_count: int|None           # Resets when the motor restarts

    voltage: float|None             # Volt
    current: float|None             # Ampere. Can be negative in case of a regenerative braking.
    temperature: float|None         # Kelvin

    rpm: int|None                   # Negative value indicates reverse rotation

    power_rating_pct: int|None      # Instant demand factor in percent (percent of maximum power); range 0% to 127%.

    esc_index: int|None

    def from_message(self, msg: dronecan.uavcan.equipment.esc.Status):
        self.error_count = msg.error_count
        self.voltage = msg.voltage
        self.current = msg.current
        self.temperature = msg.temperature
        self.rpm = msg.rpm
        self.power_rating_pct = msg.power_rating_pct
        self.esc_index = msg.esc_index
        return self

@dataclass
class ESCRPMCommand(Message):
    # Generic ESC raw command message.
    name = 'ESCRPMCommand'
    dronecan_type = dronecan.uavcan.equipment.esc.RPMCommand

    command: List[int]|None

    def from_message(self, msg: dronecan.uavcan.equipment.esc.RPMCommand):
        self.command = msg.command
        return self

@dataclass
class ESCRawCommand(Message):
    name = 'ESCRawCommand'
    dronecan_type = dronecan.uavcan.equipment.esc.RawCommand

    command: List[int]

    def from_message(self, msg: dronecan.uavcan.equipment.esc.RawCommand):
        self.command = msg.command
        return self

@dataclass
class Command(Message):
    # Nested type.
    # Single actuator command.
    name = 'Command'
    dronecan_type = dronecan.uavcan.equipment.actuator.Command
    class CommandType(Enum):
        COMMAND_TYPE_UNITLESS     = 0     # [-1, 1]
        COMMAND_TYPE_POSITION     = 1     # meter or radian
        COMMAND_TYPE_FORCE        = 2     # Newton or Newton metre
        COMMAND_TYPE_SPEED        = 3     # meter per second or radian per second

    actuator_id : int
    command_type : int # Whether the units are linear or angular depends on the actuator type.
    command_value: float # Value of the above type
    def from_message(self, msg: dronecan.uavcan.equipment.actuator.Command):
        self.actuator_id = msg.actuator_id
        self.command_type = Command.CommandType(msg.command_type)
        self.command_value = msg.command_value
        return self

@dataclass
class ArrayCommand(Message):
    name = 'ArrayCommand'
    dronecan_type = dronecan.uavcan.equipment.actuator.ArrayCommand
    command: List[Command]

    def from_message(self, msg: dronecan.uavcan.equipment.actuator.ArrayCommand):
        self.command = []
        for i in len(msg.command):
            self.command.append(Command.from_message(msg.command[i]))
        return self

@dataclass
class ArrayStatus(Message):
    # Generic actuator feedback, if available.
    name = 'ArrayStatus'
    dronecan_type = dronecan.uavcan.equipment.actuator.Status

    actuator_id: int|None
    # Whether the units are linear or angular depends on the actuator type (refer to the Command data type).
    position: float|None        # meter or radian
    force: float|None           # Newton or Newton metre
    speed: float|None           # meter per second or radian per second
    power_rating_pct: int|None                # 0 - unloaded, 100 - full load

    def from_message(self, msg: dronecan.uavcan.equipment.actuator.Status):
        self.actuator_id = msg.actuator_id
        self.position = msg.position
        self.force = msg.force
        self.speed = msg.speed
        self.power_rating_pct = msg.power_rating_pct
        return self

@dataclass
class RawImu(Message):
    name = 'RawImu'
    dronecan_type = dronecan.uavcan.equipment.ahrs.RawIMU
    timestamp: int

    integration_interval: float|None

    rate_gyro_latest: List[float]|None                 # Latest sample, radian/second
    rate_gyro_integral: List[float]|None               # Integrated samples, radian/second

    accelerometer_latest: List[float]|None             # Latest sample, meter/(second^2)
    accelerometer_integral: List[float]|None             # Latest sample, meter/(second^2)# Integrated samples, meter/(second^2)

    covariance: float

    def from_message(self, msg: dronecan.uavcan.equipment.ahrs.RawIMU):
        self.timestamp = msg.timestamp
        self.integration_interval = msg.integration_interval
        self.rate_gyro_latest = msg.rate_gyro_latest
        self.rate_gyro_integral = msg.rate_gyro_integral
        self.accelerometer_latest = msg.accelerometer_latest
        self.accelerometer_integral = msg.accelerometer_integral
        self.covariance = msg.covariance
        return self

@dataclass
class ImuVibrations(Message):
    name = 'ImuVibrations'
    dronecan_type = dronecan.uavcan.equipment.ahrs.RawIMU

    timestamp: int

    vibration: float|None

    gyro_dominant_frequency: float|None
    gyro_dominant_magnitude: float|None
    gyro_dominant_srn: float|None

    accel_dominant_frequency: float|None
    accel_dominant_magnitude: float|None
    accel_dominant_srn: float|None
    rate_gyro_latest: List[float]|None                 # Latest sample, radian/second
    rate_gyro_integral: List[float]|None               # Integrated samples, radian/second

    accelerometer_latest: List[float]|None             # Latest sample, meter/(second^2)
    accelerometer_integral: List[float]|None             # Latest sample, meter/(second^2)# Integrated samples, meter/(second^2)

    covariance: float

    def from_message(self, msg: dronecan.uavcan.equipment.ahrs.RawIMU):
        self.timestamp = msg.timestamp
        self.vibration = msg.integration_interval
        self.rate_gyro_latest = msg.rate_gyro_latest
        self.gyro_dominant_frequency = msg.rate_gyro_integral[0]
        self.gyro_dominant_magnitude = msg.rate_gyro_integral[1]
        self.gyro_dominant_srn = msg.rate_gyro_integral[2]

        self.accelerometer_latest = msg.accelerometer_latest
        self.accel_dominant_frequency = msg.accelerometer_integral[0]
        self.accel_dominant_magnitude = msg.accelerometer_integral[1]
        self.accel_dominant_srn = msg.accelerometer_integral[2]

        return self

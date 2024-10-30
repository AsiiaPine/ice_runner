import abc
import enum
import logging
from typing import Any, Dict, List
import dronecan
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class Message(abc.ABC):
    name = 'Message'
    dronecan_type = None

    @abc.abstractmethod
    def from_message(cls, data: Any) -> Any|None:
        if data is None:
            Message.logger.debug(f"Message {cls.__name__} is None")
            return None

    @abc.abstractmethod
    def to_dronecan(self)-> Any :
        pass

    def to_dict(self) -> Dict[str, Any]:
        pass

@dataclass
class NodeStatus(Message):
    """ Node status information. All UAVCAN nodes are required to publish this message periodically."""
    name = 'uavcan.protocol.NodeStatus'
    dronecan_type = dronecan.uavcan.protocol.NodeStatus

    class Mode(enum.IntEnum):
        MODE_OPERATIONAL      = 0         # Normal operating mode.
        MODE_INITIALIZATION   = 1         # Initialization is in progress; this mode is entered immediately after startup.
        MODE_MAINTENANCE      = 2         # E.g. calibration, the bootloader is running, etc.
        MODE_SOFTWARE_UPDATE  = 3         # New software/firmware is being loaded.
        MODE_OFFLINE          = 7         # The node is no longer available.
    
    class Health(enum.IntEnum):
        HEALTH_OK         = 0     # The node is functioning properly.
        HEALTH_WARNING    = 1     # A critical parameter went out of range or the node encountered a minor failure.
        HEALTH_ERROR      = 2     # The node encountered a major failure.
        HEALTH_CRITICAL   = 3     # The node suffered a fatal malfunction.

    uptime_sec: int
    health: Health
    mode: Mode

    sub_mode: int = 0 # Not used currently, keep zero when publishing, ignore when receiving.
    
    vendor_specific_status_code: int = 0 # Optional, vendor-specific node status code, e.g. a fault code or a status bitmask.

    @classmethod
    def from_message(cls, msg: dronecan.uavcan.protocol.NodeStatus):
        uptime_sec = msg.uptime_sec
        health = NodeStatus.Health(msg.health)
        mode = NodeStatus.Mode(msg.mode)
        sub_mode = msg.sub_mode
        vendor_specific_status_code = msg.vendor_specific_status_code
        return cls(uptime_sec, health, mode, sub_mode, vendor_specific_status_code)

    def to_dronecan(self) -> dronecan.uavcan.protocol.NodeStatus:
        return self.dronecan_type(uptime_sec=self.uptime_sec, health=self.health, mode=self.mode, sub_mode=self.sub_mode, vendor_specific_status_code=self.vendor_specific_status_code)

    def to_dict(self) -> Dict[str, Any]:
        super().to_dict()
        return {"uptime_sec": self.uptime_sec, "health": self.health, "mode": self.mode, "sub_mode": self.sub_mode, "vendor_specific_status_code": self.vendor_specific_status_code}

@dataclass
class CylinderStatus(Message):
    dronecan_type = dronecan.uavcan.equipment.ice.reciprocating.CylinderStatus
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

    @classmethod
    def from_message(cls, msg):
        ignition_timing_deg = msg.ignition_timing_deg
        injection_time_ms = msg.injection_time_ms
        cylinder_head_temperature = msg.cylinder_head_temperature
        exhaust_gas_temperature = msg.exhaust_gas_temperature
        lambda_coefficient = msg.lambda_coefficient
        return cls(ignition_timing_deg,
                   injection_time_ms,
                   cylinder_head_temperature,
                   exhaust_gas_temperature,
                   lambda_coefficient)

    def to_dronecan(self) -> dronecan.uavcan.equipment.ice.reciprocating.CylinderStatus:
        return dronecan.uavcan.equipment.ice.reciprocating.CylinderStatus(ignition_timing_deg=self.cylinder_status.ignition_timing_deg,
            injection_time_ms=self.cylinder_status.injection_time_ms,
            cylinder_head_temperature=self.cylinder_status.cylinder_head_temperature,
            exhaust_gas_temperature=self.cylinder_status.exhaust_gas_temperature,
            lambda_coefficient=self.cylinder_status.lambda_coefficient)

    def to_dict(self) -> Dict[str, Any]:
        super().to_dict()
        return {"ignition_timing_deg": self.cylinder_status.ignition_timing_deg,
                "injection_time_ms": self.cylinder_status.injection_time_ms,
                "cylinder_head_temperature": self.cylinder_status.cylinder_head_temperature,
                "exhaust_gas_temperature": self.cylinder_status.exhaust_gas_temperature,
                "lambda_coefficient": self.cylinder_status.lambda_coefficient}

@dataclass
class ICEReciprocatingStatus(Message):
    name = 'uavcan.equipment.ice.reciprocating.Status'
    dronecan_type = dronecan.uavcan.equipment.ice.reciprocating.Status

    class State(enum.IntEnum):
        STATE_STOPPED   = 0 # The engine is not running. This is the default state.
        STATE_STARTING  = 1 # The engine is starting. This is a transient state.
        STATE_RUNNING   = 2 # The engine is running normally.
        STATE_FAULT     = 3  # The engine can no longer function.

    class Flags(enum.IntEnum):
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

    class SparkPlugUsage(enum.IntEnum):
        SPARK_PLUG_SINGLE         = 0
        SPARK_PLUG_FIRST_ACTIVE   = 1
        SPARK_PLUG_SECOND_ACTIVE  = 2
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

    @classmethod
    def from_message(cls, msg: dronecan.uavcan.equipment.ice.reciprocating.Status):
        super().from_message(Message, msg)

        state = ICEReciprocatingStatus.State(msg.state)
        flags = msg.flags
        engine_load_percent = msg.engine_load_percent
        engine_speed_rpm = msg.engine_speed_rpm
        spark_dwell_time_ms = msg.spark_dwell_time_ms
        atmospheric_pressure_kpa = msg.atmospheric_pressure_kpa
        intake_manifold_pressure_kpa = msg.intake_manifold_pressure_kpa
        intake_manifold_temperature = msg.intake_manifold_temperature
        coolant_temperature = msg.coolant_temperature
        oil_pressure = msg.oil_pressure
        oil_temperature = msg.oil_temperature
        fuel_pressure = msg.fuel_pressure
        fuel_consumption_rate_cm3pm = msg.fuel_consumption_rate_cm3pm
        estimated_consumed_fuel_volume_cm3 = msg.estimated_consumed_fuel_volume_cm3
        throttle_position_percent = msg.throttle_position_percent
        ecu_index = msg.ecu_index
        spark_plug_usage = ICEReciprocatingStatus.SparkPlugUsage(msg.spark_plug_usage)
        cylinder_status = []
        for i in range(16):
            try:
                cylinder_status.append(CylinderStatus.from_message(msg.cylinder_status[i]))
            except IndexError:
                break
        return cls(state=state, flags=flags, engine_load_percent=engine_load_percent, engine_speed_rpm=engine_speed_rpm, spark_dwell_time_ms=spark_dwell_time_ms, atmospheric_pressure_kpa=atmospheric_pressure_kpa, intake_manifold_pressure_kpa=intake_manifold_pressure_kpa,intake_manifold_temperature=intake_manifold_temperature, coolant_temperature=coolant_temperature, oil_pressure=oil_pressure,oil_temperature=oil_temperature, fuel_pressure=fuel_pressure,fuel_consumption_rate_cm3pm=fuel_consumption_rate_cm3pm,estimated_consumed_fuel_volume_cm3=estimated_consumed_fuel_volume_cm3, throttle_position_percent=throttle_position_percent, ecu_index=ecu_index, spark_plug_usage=spark_plug_usage, cylinder_status=cylinder_status)

    def to_dronecan(self) -> dronecan.uavcan.equipment.ice.reciprocating.Status:
        return dronecan.uavcan.equipment.ice.reciprocating.Status(
            state=self.state,
            flags=self.flags,
            engine_load_percent=self.engine_load_percent,
            engine_speed_rpm=self.engine_speed_rpm,
            spark_dwell_time_ms=self.spark_dwell_time_ms,
            atmospheric_pressure_kpa=self.atmospheric_pressure_kpa,
            intake_manifold_pressure_kpa=self.intake_manifold_pressure_kpa,
            intake_manifold_temperature=self.intake_manifold_temperature,
            coolant_temperature=self.coolant_temperature,
            oil_pressure=self.oil_pressure,
            oil_temperature=self.oil_temperature,
            fuel_pressure=self.fuel_pressure,
            fuel_consumption_rate_cm3pm=self.fuel_consumption_rate_cm3pm,
            estimated_consumed_fuel_volume_cm3=self.estimated_consumed_fuel_volume_cm3,
            throttle_position_percent=self.throttle_position_percent,
            ecu_index=self.ecu_index,
            spark_plug_usage=self.spark_plug_usage,
            cylinder_status=self.cylinder_status.to_dict())

    def to_dict(self) -> Dict[str, Any]:
        super().to_dict()
        return {"state": self.state,
                "flags": self.flags,                
                "engine_load_percent": self.engine_load_percent,
                "engine_speed_rpm": self.engine_speed_rpm,
                "spark_dwell_time_ms": self.spark_dwell_time_ms,
                "atmospheric_pressure_kpa": self.atmospheric_pressure_kpa,
                "intake_manifold_pressure_kpa": self.intake_manifold_pressure_kpa,
                "intake_manifold_temperature": self.intake_manifold_temperature,
                "coolant_temperature": self.coolant_temperature,
                "oil_pressure": self.oil_pressure,
                "oil_temperature": self.oil_temperature,
                "fuel_pressure": self.fuel_pressure,
                "fuel_consumption_rate_cm3pm": self.fuel_consumption_rate_cm3pm,
                "estimated_consumed_fuel_volume_cm3": self.estimated_consumed_fuel_volume_cm3,
                "throttle_position_percent": self.throttle_position_percent,
                "ecu_index": self.ecu_index,
                "spark_plug_usage": self.spark_plug_usage,
                "cylinder_status": self.cylinder_status.to_dict()}

@dataclass
class FuelTankStatus(Message):
    name = 'uavcan.equipment.ice.FuelTankStatus'
    dronecan_type = dronecan.uavcan.equipment.ice.FuelTankStatus
    # Generic fuel tank status message.

    available_fuel_volume_percent: int     # Unit: percent, from 0% to 100%
    available_fuel_volume_cm3: float       # Unit: centimeter^3
    fuel_consumption_rate_cm3pm: float
    fuel_temperature: float|None
    fuel_tank_id: int

    @classmethod
    def from_message(cls, msg: dronecan.uavcan.equipment.ice.FuelTankStatus):
        super().from_message(Message, msg)

        available_fuel_volume_percent = msg.available_fuel_volume_percent
        available_fuel_volume_cm3 = msg.available_fuel_volume_cm3
        fuel_consumption_rate_cm3pm = msg.fuel_consumption_rate_cm3pm
        fuel_temperature = msg.fuel_temperature
        fuel_tank_id = msg.fuel_tank_id
        return cls(available_fuel_volume_percent,
                    available_fuel_volume_cm3,
                    fuel_consumption_rate_cm3pm,
                    fuel_temperature,
                    fuel_tank_id)   

    def to_dronecan(self) -> dronecan.uavcan.equipment.ice.FuelTankStatus:
        return dronecan.uavcan.equipment.ice.FuelTankStatus\
                            (available_fuel_volume_percent=self.available_fuel_volume_percent,
                                available_fuel_volume_cm3=self.available_fuel_volume_cm3,
                                fuel_consumption_rate_cm3pm=self.fuel_consumption_rate_cm3pm,
                                fuel_temperature=self.fuel_temperature,
                                fuel_tabk_id=self.fuel_tank_id)

    def to_dict(self) -> Dict[str, Any]:
        super().to_dict()
        return {"available_fuel_volume_percent": self.available_fuel_volume_percent,
                "available_fuel_volume_cm3": self.available_fuel_volume_cm3,
                "fuel_consumption_rate_cm3pm": self.fuel_consumption_rate_cm3pm,
                "fuel_temperature": self.fuel_temperature,
                "fuel_tabk_id": self.fuel_tank_id}

@dataclass
class ESCStatus(Message):
    name = 'uavcan.equipment.esc.Status'
    dronecan_type = dronecan.uavcan.equipment.esc.Status
    # Generic ESC status message.

    error_count: int|None           # Resets when the motor restarts

    voltage: float|None             # Volt
    current: float|None             # Ampere. Can be negative in case of a regenerative braking.
    temperature: float|None         # Kelvin

    rpm: int|None                   # Negative value indicates reverse rotation

    power_rating_pct: int|None      # Instant demand factor in percent (percent of maximum power); range 0% to 127%.

    esc_index: int|None

    @classmethod
    def from_message(cls, msg: dronecan.uavcan.equipment.esc.Status):
        super().from_message(Message, msg)

        error_count = msg.error_count
        voltage = msg.voltage
        current = msg.current
        temperature = msg.temperature
        rpm = msg.rpm
        power_rating_pct = msg.power_rating_pct
        esc_index = msg.esc_index
        return cls(error_count, voltage, current, temperature, rpm, power_rating_pct, esc_index)

    def to_dronecan(self) -> dronecan.uavcan.equipment.esc.Status:
        return dronecan.uavcan.equipment.esc.Status(
            error_count=self.error_count,
            voltage = self.voltage,
            current = self.current,
            temperature = self.temperature,
            rpm = self.rpm,
            power_rating_pct = self.power_rating_pct,
            esc_index = self.esc_index
        )

    def to_dict(self) -> Dict[str, Any]:
        super().to_dict()
        return {"error_count": self.error_count,
                "voltage": self.voltage,
                "current": self.current,
                "temperature": self.temperature,
                "rpm": self.rpm,
                "power_rating_pct": self.power_rating_pct,
                "esc_index": self.esc_index}

@dataclass
class ESCRPMCommand(Message):
    # Generic ESC raw command message.
    name = 'uavcan.equipment.esc.RPMCommand'
    dronecan_type = dronecan.uavcan.equipment.esc.RPMCommand

    command: List[int]|None

    @classmethod
    def from_message(cls, msg: dronecan.uavcan.equipment.esc.RPMCommand):
        super().from_message(Message, msg)

        command = msg.command
        return cls(command)

    def to_dronecan(self) -> dronecan.uavcan.equipment.esc.RPMCommand:
        return dronecan.uavcan.equipment.esc.RPMCommand(
            command=self.command
        )

    def to_dict(self) -> Dict[str, Any]:
        super().to_dict()
        return {"command": self.command}

@dataclass
class ESCRawCommand(Message):
    name = 'uavcan.equipment.esc.RawCommand'
    dronecan_type = dronecan.uavcan.equipment.esc.RawCommand

    command: List[int]

    @classmethod
    def from_message(cls, msg: dronecan.uavcan.equipment.esc.RawCommand):
        super().from_message(Message, msg)

        command = msg.command
        return cls(command)

    def to_dronecan(self) -> dronecan.uavcan.equipment.esc.RawCommand:
        return dronecan.uavcan.equipment.esc.RawCommand(command=self.command)

    def to_dict(self) -> Dict[str, Any]:
        super().to_dict()
        return {"command": self.command}

@dataclass
class ActuatorCommand(Message):
    # Nested type.
    # Single actuator command.
    name = 'uavcan.equipment.actuator.Command'
    dronecan_type = dronecan.uavcan.equipment.actuator.Command
    class CommandType(enum.IntEnum):
        COMMAND_TYPE_UNITLESS     = 0     # [-1, 1]
        COMMAND_TYPE_POSITION     = 1     # meter or radian
        COMMAND_TYPE_FORCE        = 2     # Newton or Newton metre
        COMMAND_TYPE_SPEED        = 3     # meter per second or radian per second

    actuator_id : int
    command_type : int # Whether the units are linear or angular depends on the actuator type.
    command_value: float # Value of the above type

    @classmethod
    def from_message(cls, msg: dronecan.uavcan.equipment.actuator.Command):
        super().from_message(Message, msg)

        actuator_id = msg.actuator_id
        command_type = ActuatorCommand.CommandType(msg.command_type)
        command_value = msg.command_value
        return cls(actuator_id, command_type, command_value)

    def to_dronecan(self) -> dronecan.uavcan.equipment.actuator.Command:
        return dronecan.uavcan.equipment.actuator.Command(actuator_id=self.actuator_id,
                                                          command_type=self.command_type,
                                                          command_value=self.command_value)

    def to_dict(self) -> Dict[str, Any]:
        super().to_dict()
        return {"actuator_id": self.actuator_id,
                "command_type": self.command_type,
                "command_value": self.command_value}

@dataclass
class ArrayCommand(Message):
    name = 'uavcan.equipment.actuator.ArrayCommand'
    dronecan_type = dronecan.uavcan.equipment.actuator.ArrayCommand
    commands: List[ActuatorCommand]

    @classmethod
    def from_message(cls, msg: dronecan.uavcan.equipment.actuator.ArrayCommand):
        super().from_message(Message, msg)

        commands = []
        for i in len(msg.commands):
            commands.append(ActuatorCommand.from_message(msg.commands[i]))
        return cls(commands)

    def to_dronecan(self) -> dronecan.uavcan.equipment.actuator.ArrayCommand:
        return dronecan.uavcan.equipment.actuator.ArrayCommand(commands=self.commands)

    def to_dict(self) -> Dict[str, Any]:
        super().to_dict()
        return {"commands": self.commands}

@dataclass
class ActuatorStatus(Message):
    # Generic actuator feedback, if available.
    name = 'uavcan.equipment.actuator.Status'
    dronecan_type = dronecan.uavcan.equipment.actuator.Status

    actuator_id: int|None
    # Whether the units are linear or angular depends on the actuator type (refer to the Command data type).
    position: float|None        # meter or radian
    force: float|None           # Newton or Newton metre
    speed: float|None           # meter per second or radian per second
    power_rating_pct: int|None                # 0 - unloaded, 100 - full load

    @classmethod
    def from_message(cls, msg: dronecan.uavcan.equipment.actuator.Status):
        super().from_message(Message, msg)

        actuator_id = msg.actuator_id
        position = msg.position
        force = msg.force
        speed = msg.speed
        power_rating_pct = msg.power_rating_pct
        return cls(actuator_id, position, force, speed, power_rating_pct)

    def to_dronecan(self) -> dronecan.uavcan.equipment.actuator.Status:
        return dronecan.uavcan.equipment.actuator.Status(actuator_id=self.actuator_id,
                                                         position=self.position,
                                                         force=self.force,
                                                         speed=self.speed,
                                                         power_rating_pct=self.power_rating_pct)

    def to_dict(self) -> Dict[str, Any]:
        super().to_dict()
        return {"actuator_id": self.actuator_id,
                "position": self.position,
                "force": self.force,
                "speed": self.speed,
                "power_rating_pct": self.power_rating_pct}

@dataclass
class RawImu(Message):
    name = 'uavcan.equipment.ahrs.RawIMU'
    dronecan_type = dronecan.uavcan.equipment.ahrs.RawIMU
    timestamp: int

    integration_interval: float|None

    rate_gyro_latest: List[float]|None                 # Latest sample, radian/second
    rate_gyro_integral: List[float]|None               # Integrated samples, radian/second

    accelerometer_latest: List[float]|None             # Latest sample, meter/(second^2)
    accelerometer_integral: List[float]|None             # Latest sample, meter/(second^2)# Integrated samples, meter/(second^2)

    covariance: float

    @classmethod
    def from_message(cls, msg: dronecan.uavcan.equipment.ahrs.RawIMU):
        super().from_message(Message, msg)

        timestamp = msg.timestamp
        integration_interval = msg.integration_interval
        rate_gyro_latest = msg.rate_gyro_latest
        rate_gyro_integral = msg.rate_gyro_integral
        accelerometer_latest = msg.accelerometer_latest
        accelerometer_integral = msg.accelerometer_integral
        covariance = msg.covariance
        return cls(timestamp, integration_interval, rate_gyro_latest, rate_gyro_integral, accelerometer_latest, accelerometer_integral, covariance)

    def to_dronecan(self) -> dronecan.uavcan.equipment.ahrs.RawIMU:
        return dronecan.uavcan.equipment.ahrs.RawIMU(timestamp=self.timestamp,
                                                     integration_interval=self.integration_interval,
                                                     rate_gyro_latest=self.rate_gyro_latest,
                                                     rate_gyro_integral=self.rate_gyro_integral,
                                                     accelerometer_latest=self.accelerometer_latest,
                                                     accelerometer_integral=self.accelerometer_integral,
                                                     covariance=self.covariance)

    def to_dict(self) -> Dict[str, Any]:
        super().to_dict()
        return {"timestamp": self.timestamp,
                "integration_interval": self.integration_interval,
                "rate_gyro_latest": self.rate_gyro_latest,
                "rate_gyro_integral": self.rate_gyro_integral,
                "accelerometer_latest": self.accelerometer_latest,
                "accelerometer_integral": self.accelerometer_integral,
                "covariance": self.covariance}

@dataclass
class ImuVibrations(Message):
    name = 'uavcan.equipment.ahrs.Vibrations'
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

    @classmethod
    def from_message(cls, msg: dronecan.uavcan.equipment.ahrs.RawIMU):
        super().from_message(Message, msg)

        timestamp = msg.timestamp
        vibration = msg.integration_interval
        rate_gyro_latest = msg.rate_gyro_latest
        gyro_dominant_frequency = msg.rate_gyro_integral[0]
        gyro_dominant_magnitude = msg.rate_gyro_integral[1]
        gyro_dominant_srn = msg.rate_gyro_integral[2]

        accelerometer_latest = msg.accelerometer_latest
        accel_dominant_frequency = msg.accelerometer_integral[0]
        accel_dominant_magnitude = msg.accelerometer_integral[1]
        accel_dominant_srn = msg.accelerometer_integral[2]

        return cls(timestamp, vibration, rate_gyro_latest, gyro_dominant_frequency, gyro_dominant_magnitude, gyro_dominant_srn, accelerometer_latest, accel_dominant_frequency, accel_dominant_magnitude, accel_dominant_srn)

    def to_dronecan(self) -> dronecan.uavcan.equipment.ahrs.RawIMU:
        return dronecan.uavcan.equipment.ahrs.RawIMU(timestamp=self.timestamp,
                                                     integration_interval=self.vibration,
                                                     rate_gyro_latest=self.rate_gyro_latest,
                                                     rate_gyro_integral=[
                                                        self.gyro_dominant_frequency,
                                                        self.gyro_dominant_magnitude,
                                                        self.gyro_dominant_srn],
                                                     accelerometer_latest=self.accelerometer_latest,
                                                     accelerometer_integral=[
                                                        self.accel_dominant_frequency,
                                                        self.accel_dominant_magnitude,
                                                        self.accel_dominant_srn],
                                                     covariance=self.covariance)

    def to_dict(self) -> Dict[str, Any]:
        super().to_dict()
        return {"timestamp": self.timestamp,
                "vibration": self.vibration,
                "rate_gyro_latest": self.rate_gyro_latest,
                "gyro_dominant_frequency": self.gyro_dominant_frequency,
                "gyro_dominant_magnitude": self.gyro_dominant_magnitude,
                "gyro_dominant_srn": self.gyro_dominant_srn,
                "accelerometer_latest": self.accelerometer_latest,
                "accel_dominant_frequency": self.accel_dominant_frequency,
                "accel_dominant_magnitude": self.accel_dominant_magnitude,
                "accel_dominant_srn": self.accel_dominant_srn}

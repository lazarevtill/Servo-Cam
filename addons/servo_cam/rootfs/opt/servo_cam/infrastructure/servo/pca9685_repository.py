#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PCA9685 Servo Controller Repository
Hardware implementation for servo control
"""
import time
from typing import Optional

try:
    import smbus2
    HAS_SMBUS = True
except ImportError:
    HAS_SMBUS = False

from config import settings
from domain.repositories import IServoRepository
from domain.value_objects import ServoPosition


class PCA9685Driver:
    """Low-level PCA9685 PWM driver"""

    # Register addresses
    MODE1 = 0x00
    PRESCALE = 0xFE
    LED0_ON_L = 0x06
    LED0_OFF_L = 0x08

    def __init__(self, bus_number: int = 1, address: int = 0x40, frequency: int = 50):
        self.bus = smbus2.SMBus(bus_number)
        self.address = address
        self.frequency = frequency

        # Initialize
        self.bus.write_byte_data(self.address, self.MODE1, 0x00)
        self._set_pwm_frequency(frequency)

    def _set_pwm_frequency(self, frequency_hz: int):
        """Set PWM frequency"""
        prescale = int((25000000.0 / 4096.0 / frequency_hz) - 1 + 0.5)

        old_mode = self.bus.read_byte_data(self.address, self.MODE1)
        sleep_mode = (old_mode & 0x7F) | 0x10
        self.bus.write_byte_data(self.address, self.MODE1, sleep_mode)
        self.bus.write_byte_data(self.address, self.PRESCALE, prescale)
        self.bus.write_byte_data(self.address, self.MODE1, old_mode)
        time.sleep(0.005)
        self.bus.write_byte_data(self.address, self.MODE1, old_mode | 0x80)

    def set_pwm(self, channel: int, on: int, off: int):
        """Set PWM on/off values for channel"""
        base_register = self.LED0_ON_L + 4 * channel
        self.bus.write_byte_data(self.address, base_register, on & 0xFF)
        self.bus.write_byte_data(self.address, base_register + 1, on >> 8)
        self.bus.write_byte_data(self.address, base_register + 2, off & 0xFF)
        self.bus.write_byte_data(self.address, base_register + 3, off >> 8)

    def set_pwm_ms(self, channel: int, milliseconds: float):
        """Set PWM using millisecond pulse width"""
        pulse_length_us = 1000000.0 / self.frequency / 4096.0
        pulse = int(milliseconds * 1000.0 / pulse_length_us)
        self.set_pwm(channel, 0, pulse)

    def close(self):
        """Close I2C bus"""
        self.bus.close()


class PCA9685ServoRepository(IServoRepository):
    """
    Servo repository implementation using PCA9685 PWM controller
    """

    def __init__(self):
        self.driver: Optional[PCA9685Driver] = None
        self.current_position = ServoPosition.centered()
        self._is_connected = False

        # Servo calibration
        self.min_pulse_ms = settings.SERVO_MIN_MS
        self.max_pulse_ms = settings.SERVO_MAX_MS
        self.angle_range = settings.SERVO_ANGLE_RANGE

        # Smooth movement tracking
        self.last_update_time = time.time()
        self.previous_position: Optional[ServoPosition] = None

    def connect(self) -> bool:
        """Connect to PCA9685 controller"""
        if not HAS_SMBUS:
            print("⚠ smbus2 not available")
            return False

        try:
            # Test I2C connection
            test_bus = smbus2.SMBus(1)
            test_bus.read_byte(settings.SERVO_I2C_ADDRESS)
            test_bus.close()

            # Initialize driver
            self.driver = PCA9685Driver(
                bus_number=1,
                address=settings.SERVO_I2C_ADDRESS,
                frequency=settings.SERVO_PWM_FREQUENCY
            )

            self._is_connected = True
            print(f"✓ PCA9685 connected at 0x{settings.SERVO_I2C_ADDRESS:02X}")
            return True

        except Exception as e:
            print(f"❌ PCA9685 connection failed: {e}")
            self.driver = None
            self._is_connected = False
            return False

    def disconnect(self):
        """Disconnect from controller"""
        if self.driver:
            try:
                self.driver.close()
            except Exception:
                pass
            self.driver = None

        self._is_connected = False

    def move_to(self, position: ServoPosition) -> bool:
        """Move servos to target position (immediate, no smoothing)"""
        if not self._is_connected or not self.driver:
            return False

        try:
            # Set pan servo
            pan_ms = self._angle_to_pulse(position.pan.degrees)
            self.driver.set_pwm_ms(settings.SERVO_PAN_CHANNEL, pan_ms)

            # Set tilt servo
            tilt_ms = self._angle_to_pulse(position.tilt.degrees)
            self.driver.set_pwm_ms(settings.SERVO_TILT_CHANNEL, tilt_ms)

            # Track previous position before updating
            self.previous_position = self.current_position
            self.current_position = position
            self.last_update_time = time.time()
            return True

        except Exception as e:
            print(f"⚠ Servo move error: {e}")
            return False

    def move_towards(
        self,
        target: ServoPosition,
        max_speed_dps: float,
        deadband_degrees: float,
        min_interval: float
    ) -> tuple[bool, ServoPosition]:
        """
        Smooth movement towards target with speed limiting

        Args:
            target: Target servo position
            max_speed_dps: Maximum speed in degrees per second
            deadband_degrees: Ignore movements smaller than this
            min_interval: Minimum time between updates in seconds

        Returns:
            (moved: bool, new_position: ServoPosition) - Whether servos moved and new position
        """
        if not self._is_connected or not self.driver:
            return False, self.current_position

        # Check minimum time interval
        now = time.time()
        dt = now - self.last_update_time
        if dt < min_interval:
            return False, self.current_position

        try:
            # Calculate step size based on time delta and max speed
            max_step = max_speed_dps * max(dt, 0.001)

            # Calculate new angles with speed limiting and deadband
            def calculate_step(current: float, target: float) -> float:
                delta = target - current

                # Apply deadband - ignore small movements
                if abs(delta) <= deadband_degrees:
                    return current

                # Apply speed limiting
                if delta > 0:
                    return current + min(delta, max_step)
                else:
                    return current - min(-delta, max_step)

            new_pan = calculate_step(self.current_position.pan.degrees, target.pan.degrees)
            new_tilt = calculate_step(self.current_position.tilt.degrees, target.tilt.degrees)

            # Check if any movement occurred
            pan_changed = abs(new_pan - self.current_position.pan.degrees) > 0.001
            tilt_changed = abs(new_tilt - self.current_position.tilt.degrees) > 0.001

            if not pan_changed and not tilt_changed:
                return False, self.current_position

            # Apply movements
            if pan_changed:
                pan_ms = self._angle_to_pulse(new_pan)
                self.driver.set_pwm_ms(settings.SERVO_PAN_CHANNEL, pan_ms)

            if tilt_changed:
                tilt_ms = self._angle_to_pulse(new_tilt)
                self.driver.set_pwm_ms(settings.SERVO_TILT_CHANNEL, tilt_ms)

            # Create new position
            from datetime import datetime
            from domain.value_objects import Angle
            new_position = ServoPosition(
                pan=Angle(new_pan),
                tilt=Angle(new_tilt),
                timestamp=datetime.now()
            )

            # Track previous position before updating
            self.previous_position = self.current_position
            self.current_position = new_position
            self.last_update_time = now

            return True, new_position

        except Exception as e:
            print(f"⚠ Servo move error: {e}")
            return False, self.current_position

    def get_previous_position(self) -> Optional[ServoPosition]:
        """Get the previous servo position (for webhook comparison)"""
        return self.previous_position

    def _angle_to_pulse(self, angle_degrees: float) -> float:
        """Convert angle to pulse width in milliseconds"""
        # Clamp angle to valid range
        angle = max(0.0, min(self.angle_range, angle_degrees))

        # Linear interpolation
        ratio = angle / self.angle_range
        pulse_ms = self.min_pulse_ms + ratio * (self.max_pulse_ms - self.min_pulse_ms)

        return pulse_ms

    def get_current_position(self) -> ServoPosition:
        """Get current position"""
        return self.current_position

    def is_connected(self) -> bool:
        """Check if connected"""
        return self._is_connected


class MockServoRepository(IServoRepository):
    """
    Mock servo repository for testing without hardware
    """

    def __init__(self):
        self.current_position = ServoPosition.centered()
        self._is_connected = False
        self.last_update_time = time.time()
        self.previous_position: Optional[ServoPosition] = None

    def connect(self) -> bool:
        self._is_connected = True
        print("✓ Mock servo connected")
        return True

    def disconnect(self):
        self._is_connected = False

    def move_to(self, position: ServoPosition) -> bool:
        if not self._is_connected:
            return False
        self.previous_position = self.current_position
        self.current_position = position
        self.last_update_time = time.time()
        return True

    def move_towards(
        self,
        target: ServoPosition,
        max_speed_dps: float,
        deadband_degrees: float,
        min_interval: float
    ) -> tuple[bool, ServoPosition]:
        """Mock smooth movement"""
        if not self._is_connected:
            return False, self.current_position

        now = time.time()
        dt = now - self.last_update_time
        if dt < min_interval:
            return False, self.current_position

        # Simple mock: just move to target
        self.previous_position = self.current_position
        self.current_position = target
        self.last_update_time = now
        return True, target

    def get_previous_position(self) -> Optional[ServoPosition]:
        return self.previous_position

    def get_current_position(self) -> ServoPosition:
        return self.current_position

    def is_connected(self) -> bool:
        return self._is_connected


__all__ = ['PCA9685ServoRepository', 'MockServoRepository']

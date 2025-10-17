"""Binary sensor platform for Servo Security Camera integration."""
import logging
from typing import Optional

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ServoCamCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Servo Camera binary sensors from a config entry."""
    coordinator: ServoCamCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = [
        MonitoringActiveBinarySensor(coordinator, entry),
        PatrolActiveBinarySensor(coordinator, entry),
        ServoConnectedBinarySensor(coordinator, entry),
        CameraActiveBinarySensor(coordinator, entry),
        MotionDetectedBinarySensor(coordinator, entry),
    ]

    async_add_entities(sensors)


class ServoCamBinarySensorBase(CoordinatorEntity[ServoCamCoordinator], BinarySensorEntity):
    """Base class for Servo Camera binary sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ServoCamCoordinator,
        entry: ConfigEntry,
        sensor_type: str,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{entry.entry_id}_{sensor_type}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Servo Security Camera",
        }


class MonitoringActiveBinarySensor(ServoCamBinarySensorBase):
    """Binary sensor for monitoring active state."""

    _attr_name = "Monitoring active"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:eye"

    def __init__(self, coordinator: ServoCamCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "monitoring_active")

    @property
    def is_on(self) -> bool:
        """Return true if monitoring is active."""
        return self.coordinator.data.get("monitoring_active", False)


class PatrolActiveBinarySensor(ServoCamBinarySensorBase):
    """Binary sensor for patrol active state."""

    _attr_name = "Patrol active"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:routes"

    def __init__(self, coordinator: ServoCamCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "patrol_active")

    @property
    def is_on(self) -> bool:
        """Return true if patrol is active."""
        # Patrol is active if monitoring is active and PATROL_ENABLED
        return (
            self.coordinator.data.get("monitoring_active", False)
            and self.coordinator.data.get("patrol_enabled", False)
        )


class ServoConnectedBinarySensor(ServoCamBinarySensorBase):
    """Binary sensor for servo connection state."""

    _attr_name = "Servo connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_icon = "mdi:connection"

    def __init__(self, coordinator: ServoCamCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "servo_connected")

    @property
    def is_on(self) -> bool:
        """Return true if servo is connected."""
        return self.coordinator.data.get("servo_connected", False)


class CameraActiveBinarySensor(ServoCamBinarySensorBase):
    """Binary sensor for camera active state."""

    _attr_name = "Camera active"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:camera"

    def __init__(self, coordinator: ServoCamCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "camera_active")

    @property
    def is_on(self) -> bool:
        """Return true if camera is active."""
        return self.coordinator.data.get("camera_active", False)


class MotionDetectedBinarySensor(ServoCamBinarySensorBase):
    """Binary sensor for motion detection state."""

    _attr_name = "Motion detected"
    _attr_device_class = BinarySensorDeviceClass.MOTION
    _attr_icon = "mdi:motion-sensor"

    def __init__(self, coordinator: ServoCamCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "motion_detected")

    @property
    def is_on(self) -> bool:
        """Return true if motion is currently detected."""
        # Check recent motion within last 5 seconds
        motion_history = self.coordinator.data.get("recent_motions", [])
        if not motion_history:
            return False

        # Motion is "active" if detected in last update cycle
        return len(motion_history) > 0

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional attributes."""
        motion_history = self.coordinator.data.get("recent_motions", [])
        if motion_history:
            last_motion = motion_history[-1]
            return {
                "classification": last_motion.get("classification"),
                "threat_level": last_motion.get("threat_level"),
                "confidence": last_motion.get("confidence"),
                "timestamp": last_motion.get("timestamp"),
            }
        return {}

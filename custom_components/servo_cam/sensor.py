"""Sensor platform for Servo Security Camera integration."""
import logging
from typing import Optional

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEGREE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    ATTR_MOTION_CLASSIFICATION,
    ATTR_MOTION_THREAT_LEVEL,
    ATTR_MOTION_CONFIDENCE,
    ATTR_MOTION_SPEED,
    ATTR_PAN_ANGLE,
    ATTR_TILT_ANGLE,
)
from .coordinator import ServoCamCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Servo Camera sensors from a config entry."""
    coordinator: ServoCamCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = [
        PanAngleSensor(coordinator, entry),
        TiltAngleSensor(coordinator, entry),
        MotionCountSensor(coordinator, entry),
        WebhookCountSensor(coordinator, entry),
        SessionDurationSensor(coordinator, entry),
        FrameCountSensor(coordinator, entry),
        LastMotionClassificationSensor(coordinator, entry),
        LastMotionThreatSensor(coordinator, entry),
        WebhookQueueSensor(coordinator, entry),
    ]

    async_add_entities(sensors)


class ServoCamSensorBase(CoordinatorEntity[ServoCamCoordinator], SensorEntity):
    """Base class for Servo Camera sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ServoCamCoordinator,
        entry: ConfigEntry,
        sensor_type: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{entry.entry_id}_{sensor_type}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Servo Security Camera",
        }


class PanAngleSensor(ServoCamSensorBase):
    """Sensor for pan angle."""

    _attr_name = "Pan angle"
    _attr_native_unit_of_measurement = DEGREE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:pan"

    def __init__(self, coordinator: ServoCamCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "pan_angle")

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        return self.coordinator.data.get("current_pan")


class TiltAngleSensor(ServoCamSensorBase):
    """Sensor for tilt angle."""

    _attr_name = "Tilt angle"
    _attr_native_unit_of_measurement = DEGREE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:angle-acute"

    def __init__(self, coordinator: ServoCamCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "tilt_angle")

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        return self.coordinator.data.get("current_tilt")


class MotionCountSensor(ServoCamSensorBase):
    """Sensor for motion detection count."""

    _attr_name = "Motion detections"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:motion-sensor"

    def __init__(self, coordinator: ServoCamCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "motion_count")

    @property
    def native_value(self) -> Optional[int]:
        """Return the state of the sensor."""
        return self.coordinator.data.get("motion_count", 0)


class WebhookCountSensor(ServoCamSensorBase):
    """Sensor for webhook/alert count."""

    _attr_name = "Alerts sent"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:bell-alert"

    def __init__(self, coordinator: ServoCamCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "webhook_count")

    @property
    def native_value(self) -> Optional[int]:
        """Return the state of the sensor."""
        return self.coordinator.data.get("webhooks_sent", 0)


class SessionDurationSensor(ServoCamSensorBase):
    """Sensor for session duration."""

    _attr_name = "Session duration"
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:timer"

    def __init__(self, coordinator: ServoCamCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "session_duration")

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        return self.coordinator.data.get("session_duration", 0)


class FrameCountSensor(ServoCamSensorBase):
    """Sensor for frame count."""

    _attr_name = "Frames processed"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:camera-burst"

    def __init__(self, coordinator: ServoCamCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "frame_count")

    @property
    def native_value(self) -> Optional[int]:
        """Return the state of the sensor."""
        return self.coordinator.data.get("frame_count", 0)


class LastMotionClassificationSensor(ServoCamSensorBase):
    """Sensor for last motion classification."""

    _attr_name = "Last motion classification"
    _attr_icon = "mdi:tag"

    def __init__(self, coordinator: ServoCamCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "last_motion_classification")

    @property
    def native_value(self) -> Optional[str]:
        """Return the state of the sensor."""
        # Get from last motion history
        motion_history = self.coordinator.data.get("recent_motions", [])
        if motion_history:
            last_motion = motion_history[-1]
            return last_motion.get("classification", "unknown")
        return None

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional attributes."""
        motion_history = self.coordinator.data.get("recent_motions", [])
        if motion_history:
            last_motion = motion_history[-1]
            return {
                ATTR_MOTION_CONFIDENCE: last_motion.get("confidence"),
                ATTR_MOTION_SPEED: last_motion.get("speed"),
                "timestamp": last_motion.get("timestamp"),
            }
        return {}


class LastMotionThreatSensor(ServoCamSensorBase):
    """Sensor for last motion threat level."""

    _attr_name = "Last motion threat level"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:shield-alert"

    def __init__(self, coordinator: ServoCamCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "last_motion_threat")

    @property
    def native_value(self) -> Optional[float]:
        """Return the state of the sensor."""
        motion_history = self.coordinator.data.get("recent_motions", [])
        if motion_history:
            last_motion = motion_history[-1]
            return last_motion.get("threat_level")
        return None


class WebhookQueueSensor(ServoCamSensorBase):
    """Sensor for webhook queue size."""

    _attr_name = "Alert queue size"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:buffer"

    def __init__(self, coordinator: ServoCamCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "webhook_queue")

    @property
    def native_value(self) -> Optional[int]:
        """Return the state of the sensor."""
        return self.coordinator.data.get("webhook_queue_size", 0)

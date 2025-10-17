"""Camera platform for Servo Security Camera integration."""
import logging
from typing import Optional

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ATTR_PAN_ANGLE, ATTR_TILT_ANGLE
from .coordinator import ServoCamCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Servo Camera from a config entry."""
    coordinator: ServoCamCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([ServoCameraEntity(coordinator, entry)])


class ServoCameraEntity(CoordinatorEntity[ServoCamCoordinator], Camera):
    """Representation of a Servo Security Camera."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = CameraEntityFeature.ON_OFF | CameraEntityFeature.STREAM

    def __init__(
        self,
        coordinator: ServoCamCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the camera."""
        super().__init__(coordinator)
        Camera.__init__(self)

        self._attr_unique_id = f"{entry.entry_id}_camera"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Servo Security Camera",
            "manufacturer": "Custom",
            "model": "Servo Cam v1.0",
            "sw_version": "1.0.0",
        }

        # Motion detection is always enabled (handled by the system)
        self._motion_detection_enabled = True

    @property
    def is_on(self) -> bool:
        """Return true if camera is on (camera is active)."""
        return self.coordinator.data.get("camera_active", False)

    @property
    def motion_detection_enabled(self) -> bool:
        """Return the camera motion detection status."""
        return self._motion_detection_enabled

    @property
    def is_streaming(self) -> bool:
        """Return true if currently streaming."""
        # Streaming is available when monitoring is active
        return self.coordinator.data.get("monitoring_active", False)

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional state attributes."""
        data = self.coordinator.data
        return {
            ATTR_PAN_ANGLE: data.get("current_pan", 0),
            ATTR_TILT_ANGLE: data.get("current_tilt", 0),
            "servo_connected": data.get("servo_connected", False),
            "monitoring_active": data.get("monitoring_active", False),
            "patrol_enabled": data.get("patrol_enabled", False),
            "patrol_active": data.get("patrol_active", False),
            "frame_count": data.get("frame_count", 0),
            "motion_count": data.get("motion_count", 0),
            "webhook_count": data.get("webhooks_sent", 0),
            "session_duration": data.get("session_duration", 0),
            "webhook_queue_size": data.get("webhook_queue_size", 0),
            "motion_detected": data.get("motion_detected", False),
            "recent_motion_events": data.get("recent_motion_events", 0),
            "recent_motions": data.get("recent_motions", []),
            "last_motion_timestamp": data.get("last_motion_timestamp"),
            "patrol_positions": data.get("patrol_positions", 0),
        }

    async def async_camera_image(
        self, width: Optional[int] = None, height: Optional[int] = None
    ) -> Optional[bytes]:
        """Return a still image from the camera."""
        return await self.coordinator.async_get_snapshot()

    async def stream_source(self) -> Optional[str]:
        """Return the stream source (MJPEG stream URL)."""
        # Return MJPEG stream URL for direct streaming
        return await self.coordinator.async_get_mjpeg_stream()

    @property
    def use_stream_for_stills(self) -> bool:
        """Use stream for still images (more efficient)."""
        # Use dedicated snapshot endpoint for better performance
        return False

    @property
    def frame_interval(self) -> float:
        """Return the interval between frames (for polling camera_image)."""
        # Update every 0.5 seconds when polling
        return 0.5

    async def async_turn_on(self) -> None:
        """Turn on camera (start monitoring)."""
        await self.coordinator.async_start_monitoring()

    async def async_turn_off(self) -> None:
        """Turn off camera (stop monitoring)."""
        await self.coordinator.async_stop_monitoring()

    async def async_enable_motion_detection(self) -> None:
        """Enable motion detection (always enabled)."""
        # Motion detection is always active in the backend
        self._motion_detection_enabled = True

    async def async_disable_motion_detection(self) -> None:
        """Disable motion detection."""
        # Motion detection is always active but we can track the preference
        self._motion_detection_enabled = False

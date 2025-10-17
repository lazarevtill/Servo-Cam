"""
Servo Security Camera Integration for Home Assistant.

This integration provides a full-featured security camera with:
- Pan/tilt servo control
- Intelligent motion detection with classification
- Scene change detection with brightness normalization
- Autonomous patrol mode
- Priority-based webhook/event system
"""
import logging
from typing import Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, CONF_HOST, CONF_PORT
from .coordinator import ServoCamCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.CAMERA,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Servo Camera from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]

    coordinator = ServoCamCoordinator(hass, host, port)

    # Test connection
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.error("Failed to connect to Servo Camera at %s:%s: %s", host, port, err)
        raise ConfigEntryNotReady from err

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services (only once globally)
    if not hass.services.has_service(DOMAIN, "move_servo"):
        await async_setup_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()

    return unload_ok


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register integration services."""
    import voluptuous as vol
    from homeassistant.helpers import config_validation as cv

    async def handle_move_servo(call):
        """Handle move_servo service call."""
        # Get coordinator for the first entry (works with single camera)
        entry_id = next(iter(hass.data[DOMAIN]))
        coordinator: ServoCamCoordinator = hass.data[DOMAIN][entry_id]

        pan = call.data.get("pan")
        tilt = call.data.get("tilt")
        await coordinator.async_move_servo(pan, tilt)

    async def handle_preset_position(call):
        """Handle preset_position service call."""
        entry_id = next(iter(hass.data[DOMAIN]))
        coordinator: ServoCamCoordinator = hass.data[DOMAIN][entry_id]

        position = call.data.get("position")
        await coordinator.async_preset_position(position)

    async def handle_start_patrol(call):
        """Handle start_patrol service call."""
        entry_id = next(iter(hass.data[DOMAIN]))
        coordinator: ServoCamCoordinator = hass.data[DOMAIN][entry_id]

        await coordinator.async_start_patrol()

    async def handle_stop_patrol(call):
        """Handle stop_patrol service call."""
        entry_id = next(iter(hass.data[DOMAIN]))
        coordinator: ServoCamCoordinator = hass.data[DOMAIN][entry_id]

        await coordinator.async_stop_patrol()

    async def handle_center_camera(call):
        """Handle center_camera service call."""
        entry_id = next(iter(hass.data[DOMAIN]))
        coordinator: ServoCamCoordinator = hass.data[DOMAIN][entry_id]

        await coordinator.async_center_camera()

    # Register services
    hass.services.async_register(
        DOMAIN,
        "move_servo",
        handle_move_servo,
        schema=vol.Schema({
            vol.Required("pan"): vol.All(vol.Coerce(float), vol.Range(min=0, max=180)),
            vol.Required("tilt"): vol.All(vol.Coerce(float), vol.Range(min=0, max=180)),
        }),
    )

    hass.services.async_register(
        DOMAIN,
        "preset_position",
        handle_preset_position,
        schema=vol.Schema({
            vol.Required("position"): cv.string,
        }),
    )

    hass.services.async_register(DOMAIN, "start_patrol", handle_start_patrol)
    hass.services.async_register(DOMAIN, "stop_patrol", handle_stop_patrol)
    hass.services.async_register(DOMAIN, "center_camera", handle_center_camera)

    _LOGGER.info("Registered Servo Camera services")

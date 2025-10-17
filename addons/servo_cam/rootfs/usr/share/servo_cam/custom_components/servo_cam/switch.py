"""Switch platform for Servo Security Camera integration."""
import logging
from typing import Any, Optional

from homeassistant.components.switch import SwitchEntity
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
    """Set up Servo Camera switches from a config entry."""
    coordinator: ServoCamCoordinator = hass.data[DOMAIN][entry.entry_id]

    switches = [
        MonitoringSwitch(coordinator, entry),
        PatrolSwitch(coordinator, entry),
    ]

    async_add_entities(switches)


class ServoCamSwitchBase(CoordinatorEntity[ServoCamCoordinator], SwitchEntity):
    """Base class for Servo Camera switches."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ServoCamCoordinator,
        entry: ConfigEntry,
        switch_type: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{entry.entry_id}_{switch_type}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Servo Security Camera",
        }


class MonitoringSwitch(ServoCamSwitchBase):
    """Switch for monitoring mode."""

    _attr_name = "Monitoring"
    _attr_icon = "mdi:eye"

    def __init__(self, coordinator: ServoCamCoordinator, entry: ConfigEntry) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, entry, "monitoring")

    @property
    def is_on(self) -> bool:
        """Return true if monitoring is on."""
        return self.coordinator.data.get("monitoring_active", False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on monitoring."""
        await self.coordinator.async_start_monitoring()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off monitoring."""
        await self.coordinator.async_stop_monitoring()

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional state attributes."""
        return {
            "motion_count": self.coordinator.data.get("motion_count", 0),
            "session_duration": self.coordinator.data.get("session_duration", 0),
            "webhooks_sent": self.coordinator.data.get("webhooks_sent", 0),
        }


class PatrolSwitch(ServoCamSwitchBase):
    """Switch for patrol mode."""

    _attr_name = "Patrol mode"
    _attr_icon = "mdi:routes"

    def __init__(self, coordinator: ServoCamCoordinator, entry: ConfigEntry) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, entry, "patrol")

    @property
    def is_on(self) -> bool:
        """Return true if patrol is on."""
        return self.coordinator.data.get("patrol_enabled", False)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Patrol only available when monitoring is active
        return self.coordinator.data.get("monitoring_active", False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on patrol."""
        await self.coordinator.async_start_patrol()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off patrol."""
        await self.coordinator.async_stop_patrol()

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional state attributes."""
        return {
            "patrol_positions": self.coordinator.data.get("patrol_positions", 15),
        }

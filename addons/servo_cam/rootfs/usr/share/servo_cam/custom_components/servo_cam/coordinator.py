"""Data update coordinator for Servo Security Camera."""
import asyncio
import logging
from datetime import timedelta
from typing import Any, Optional

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL, PRESET_POSITIONS

_LOGGER = logging.getLogger(__name__)


class ServoCamCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Servo Camera data from the API."""

    def __init__(self, hass: HomeAssistant, host: str, port: int) -> None:
        """Initialize coordinator."""
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self._session: Optional[aiohttp.ClientSession] = None

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    @property
    def session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def async_shutdown(self) -> None:
        """Clean up resources."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API."""
        try:
            async with asyncio.timeout(10):
                async with self.session.get(f"{self.base_url}/status") as response:
                    if response.status != 200:
                        raise UpdateFailed(f"Error fetching data: {response.status}")
                    return await response.json()
        except asyncio.TimeoutError as err:
            raise UpdateFailed("Timeout fetching data") from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def async_get_snapshot(self) -> Optional[bytes]:
        """Get current camera snapshot."""
        try:
            async with asyncio.timeout(10):
                async with self.session.get(f"{self.base_url}/snapshot") as response:
                    if response.status == 200:
                        return await response.read()
        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.error("Error fetching snapshot: %s", err)
        return None

    async def async_get_mjpeg_stream(self) -> str:
        """Get MJPEG stream URL."""
        return f"{self.base_url}/video_feed"

    async def async_move_servo(self, pan: float, tilt: float) -> bool:
        """Move servo to specific angles."""
        try:
            async with asyncio.timeout(10):
                async with self.session.post(
                    f"{self.base_url}/servo/move",
                    json={"pan": pan, "tilt": tilt}
                ) as response:
                    if response.status == 200:
                        await self.async_request_refresh()
                        return True
                    _LOGGER.error("Failed to move servo: %s", response.status)
        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.error("Error moving servo: %s", err)
        return False

    async def async_preset_position(self, position: str) -> bool:
        """Move to preset position."""
        if position not in PRESET_POSITIONS:
            _LOGGER.error("Unknown preset position: %s", position)
            return False

        preset = PRESET_POSITIONS[position]
        return await self.async_move_servo(preset["pan"], preset["tilt"])

    async def async_center_camera(self) -> bool:
        """Center the camera."""
        return await self.async_preset_position("center")

    async def async_start_monitoring(self) -> bool:
        """Start monitoring mode."""
        try:
            async with asyncio.timeout(10):
                async with self.session.post(f"{self.base_url}/monitoring/start") as response:
                    if response.status == 200:
                        await self.async_request_refresh()
                        return True
        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.error("Error starting monitoring: %s", err)
        return False

    async def async_stop_monitoring(self) -> bool:
        """Stop monitoring mode."""
        try:
            async with asyncio.timeout(10):
                async with self.session.post(f"{self.base_url}/monitoring/stop") as response:
                    if response.status == 200:
                        await self.async_request_refresh()
                        return True
        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.error("Error stopping monitoring: %s", err)
        return False

    async def async_start_patrol(self) -> bool:
        """Start patrol mode."""
        try:
            async with asyncio.timeout(10):
                async with self.session.post(f"{self.base_url}/config", json={"PATROL_ENABLED": True}) as response:
                    if response.status == 200:
                        await self.async_request_refresh()
                        return True
        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.error("Error starting patrol: %s", err)
        return False

    async def async_stop_patrol(self) -> bool:
        """Stop patrol mode."""
        try:
            async with asyncio.timeout(10):
                async with self.session.post(f"{self.base_url}/config", json={"PATROL_ENABLED": False}) as response:
                    if response.status == 200:
                        await self.async_request_refresh()
                        return True
        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.error("Error stopping patrol: %s", err)
        return False

    async def async_get_config(self) -> Optional[dict]:
        """Get current configuration."""
        try:
            async with asyncio.timeout(10):
                async with self.session.get(f"{self.base_url}/config") as response:
                    if response.status == 200:
                        return await response.json()
        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.error("Error fetching config: %s", err)
        return None

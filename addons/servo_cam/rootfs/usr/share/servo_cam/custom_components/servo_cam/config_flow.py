"""Config flow for Servo Security Camera integration."""
import logging
from typing import Any

import aiohttp
import asyncio
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import (
    DOMAIN,
    DEFAULT_HOST,
    DEFAULT_PORT,
    CONF_HOST,
    CONF_PORT,
    ZEROCONF_TYPE,
)

_LOGGER = logging.getLogger(__name__)


class ServoCamConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Servo Security Camera."""

    VERSION = 1
    _discovered_data: dict[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            error = await self._async_validate_connection(host, port)
            if error is None:
                await self.async_set_unique_id(f"{host}_{port}")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Servo Camera ({host})",
                    data=user_input,
                )

            errors["base"] = error

        # Show form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
            }),
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle Zeroconf discovery."""

        if discovery_info.type != ZEROCONF_TYPE:
            return self.async_abort(reason="not_servo_cam")

        ip_address = discovery_info.ip_address
        host = str(ip_address or discovery_info.host)
        port = discovery_info.port
        raw_properties = discovery_info.properties or {}
        properties = {
            (key.decode() if isinstance(key, bytes) else key): value
            for key, value in raw_properties.items()
        }

        discovery_uuid = properties.get("uuid")
        if isinstance(discovery_uuid, bytes):
            discovery_uuid = discovery_uuid.decode()

        unique_id = discovery_uuid or f"{host}_{port}"

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        name = properties.get("name") or discovery_info.name or host
        if isinstance(name, bytes):
            name = name.decode()

        self._discovered_data = {CONF_HOST: host, CONF_PORT: port, "name": name}
        self.context["title_placeholders"] = {"name": name, "host": host}

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle confirmation of discovered device."""

        if self._discovered_data is None:
            return self.async_abort(reason="unknown")

        errors: dict[str, str] = {}
        host: str = self._discovered_data[CONF_HOST]
        port: int = self._discovered_data[CONF_PORT]

        if user_input is not None:
            error = await self._async_validate_connection(host, port)
            if error is None:
                return self.async_create_entry(
                    title=f"Servo Camera ({host})",
                    data={CONF_HOST: host, CONF_PORT: port},
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "host": host,
                "port": port,
                "name": self._discovered_data.get("name", host),
            },
            data_schema=vol.Schema({}),
            errors=errors,
        )

    async def _async_validate_connection(self, host: str, port: int) -> str | None:
        """Validate connection to the Servo Camera API."""

        try:
            async with asyncio.timeout(10):
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"http://{host}:{port}/healthz") as response:
                        if response.status == 200:
                            return None
                        return "cannot_connect"
        except asyncio.TimeoutError:
            return "timeout_connect"
        except aiohttp.ClientError:
            return "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception while validating connection")
            return "unknown"

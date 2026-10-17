"""Config flow for J.A.R.V.I.S. Assist."""
from __future__ import annotations

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import DOMAIN

CONF_BASE_URL = "base_url"
CONF_API_KEY  = "api_key"
CONF_MODEL    = "model"
CONF_TIMEOUT  = "timeout"

DEFAULT_BASE_URL = "http://10.70.10.170:10001"  # ${IP_SYSTEM_AGENT}:${AGENT_PORT} (br0 LAN — reachable from HA VM)
DEFAULT_MODEL    = "system-agent"
DEFAULT_TIMEOUT  = 120


async def _test_connection(hass: HomeAssistant, base_url: str, api_key: str) -> str | None:
    """Return None on success, or an error key string."""
    session = async_get_clientsession(hass)
    try:
        async with session.get(
            f"{base_url.rstrip('/')}/health",
            timeout=aiohttp.ClientTimeout(total=5),
        ) as resp:
            if resp.status != 200:
                return "cannot_connect"
    except aiohttp.ClientConnectorError:
        return "cannot_connect"
    except Exception:
        return "unknown"

    # Verify /v1/models responds (confirms OpenAI-compat layer is live)
    try:
        async with session.get(
            f"{base_url.rstrip('/')}/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=aiohttp.ClientTimeout(total=5),
        ) as resp:
            if resp.status == 401:
                return "invalid_auth"
            if resp.status != 200:
                return "cannot_connect"
    except Exception:
        return "unknown"

    return None


class JarvisAssistConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for J.A.R.V.I.S. Assist."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            error = await _test_connection(
                self.hass,
                user_input[CONF_BASE_URL],
                user_input[CONF_API_KEY],
            )
            if error:
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title="J.A.R.V.I.S.",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BASE_URL, default=DEFAULT_BASE_URL): str,
                    vol.Required(CONF_API_KEY): str,
                    vol.Optional(CONF_MODEL, default=DEFAULT_MODEL): str,
                    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): int,
                }
            ),
            errors=errors,
        )

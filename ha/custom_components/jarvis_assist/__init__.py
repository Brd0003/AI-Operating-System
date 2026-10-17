"""J.A.R.V.I.S. Assist Integration for Home Assistant."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

DOMAIN = "jarvis_assist"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Forward the config entry setup to the conversation platform."""
    await hass.config_entries.async_forward_entry_setups(entry, ["conversation"])
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, ["conversation"])

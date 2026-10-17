"""JARVIS ConversationEntity — plugs into Home Assistant Assist pipeline."""
from __future__ import annotations

import logging
import uuid
from typing import Literal

import aiohttp
from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .config_flow import CONF_API_KEY, CONF_BASE_URL, CONF_MODEL, CONF_TIMEOUT

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up J.A.R.V.I.S. conversation agent from a config entry."""
    agent = JarvisConversationEntity(hass, config_entry)
    async_add_entities([agent])


class JarvisConversationEntity(
    conversation.ConversationEntity,
):
    """Routes Assist voice/text queries through the system-agent swarm."""

    _attr_has_entity_name = True
    _attr_name = "J.A.R.V.I.S."

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._attr_unique_id = entry.entry_id

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        return "*"

    async def async_process(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        base_url = self.entry.data[CONF_BASE_URL].rstrip("/")
        api_key  = self.entry.data[CONF_API_KEY]
        model    = self.entry.data.get(CONF_MODEL, "system-agent")
        timeout  = self.entry.data.get(CONF_TIMEOUT, 120)

        thread_id = user_input.conversation_id or str(uuid.uuid4())

        payload = {
            "model":    model,
            "stream":   False,
            "messages": [{"role": "user", "content": user_input.text}],
        }

        session = async_get_clientsession(self.hass)

        try:
            async with session.post(
                f"{base_url}/v1/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type":  "application/json",
                    "X-Thread-ID":   thread_id,
                },
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                if resp.status == 401:
                    _LOGGER.error("JARVIS: 401 Unauthorized — check SYSTEM_AGENT_KEY")
                    return self._error_result(user_input, "Authentication failed.")
                if resp.status != 200:
                    body = await resp.text()
                    _LOGGER.error("JARVIS: HTTP %s — %s", resp.status, body[:200])
                    return self._error_result(user_input, f"Agent returned HTTP {resp.status}.")
                data = await resp.json()

        except aiohttp.ClientConnectorError as exc:
            _LOGGER.error("JARVIS: connection error — %s", exc)
            return self._error_result(user_input, "Cannot reach J.A.R.V.I.S. agent.")
        except TimeoutError:
            _LOGGER.error("JARVIS: request timed out after %ss", timeout)
            return self._error_result(user_input, "J.A.R.V.I.S. did not respond in time.")

        try:
            reply = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            _LOGGER.error("JARVIS: unexpected response shape — %s | %s", exc, data)
            return self._error_result(user_input, "Unexpected response from agent.")

        response = intent.IntentResponse(language=user_input.language)
        response.async_set_speech(reply)
        return conversation.ConversationResult(
            response=response,
            conversation_id=thread_id,
        )

    def _error_result(
        self,
        user_input: conversation.ConversationInput,
        message: str,
    ) -> conversation.ConversationResult:
        response = intent.IntentResponse(language=user_input.language)
        response.async_set_error(
            intent.IntentResponseErrorCode.UNKNOWN,
            message,
        )
        return conversation.ConversationResult(
            response=response,
            conversation_id=user_input.conversation_id,
        )

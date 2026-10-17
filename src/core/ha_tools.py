"""
core/ha_tools.py — Home Assistant tool suite for the system-agent executor.

These tools give J.A.R.V.I.S. direct read/write access to Home Assistant
via its REST API, using the long-lived token already in the environment.

Design principles:
  - Every tool is a self-contained async function decorated with @tool.
  - All config comes from env vars — nothing hardcoded.
  - Errors are returned as descriptive strings, never raised, so the
    executor's tool loop can surface them to the LLM cleanly.
  - Tools are intentionally granular: call_ha_service handles ALL
    service calls (lights, switches, climate, locks, etc.); separate
    tools handle state reads, area listing, and entity search so the
    LLM doesn't have to guess entity IDs.

Adding a new harness later follows the same pattern:
  1. Create core/<harness>_tools.py with @tool functions.
  2. Import and append in core/harness_registry.py (see bottom of this file).
  3. The executor picks them up automatically via get_all_harness_tools().
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

import aiohttp
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# ── Configuration from environment ──────────────────────────────────────────
_HA_URL   = os.environ.get("URL_HOME_ASSISTANT", "http://10.70.10.14").rstrip("/")
_HA_TOKEN = os.environ.get("HA_LONG_LIVED_TOKEN", "")

def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_HA_TOKEN}",
        "Content-Type": "application/json",
    }

async def _ha_get(path: str, timeout: int = 10) -> tuple[int, Any]:
    """Return (status_code, parsed_json_or_text)."""
    url = f"{_HA_URL}{path}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, headers=_headers(), timeout=aiohttp.ClientTimeout(total=timeout)
            ) as resp:
                try:
                    body = await resp.json()
                except Exception:
                    body = await resp.text()
                return resp.status, body
    except aiohttp.ClientConnectorError as exc:
        logger.error("ha_tools: GET %s connection error: %s", path, exc)
        return 0, f"Connection error: {exc}"
    except Exception as exc:
        logger.error("ha_tools: GET %s unexpected error: %s", path, exc)
        return 0, f"Unexpected error: {exc}"

async def _ha_post(path: str, body: dict, timeout: int = 15) -> tuple[int, Any]:
    """Return (status_code, parsed_json_or_text)."""
    url = f"{_HA_URL}{path}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=body,
                headers=_headers(),
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                try:
                    result = await resp.json()
                except Exception:
                    result = await resp.text()
                return resp.status, result
    except aiohttp.ClientConnectorError as exc:
        logger.error("ha_tools: POST %s connection error: %s", path, exc)
        return 0, f"Connection error: {exc}"
    except Exception as exc:
        logger.error("ha_tools: POST %s unexpected error: %s", path, exc)
        return 0, f"Unexpected error: {exc}"

# ── Light wrapper functions (for backward compatibility with executor.py) ─────

@tool
async def turn_on_light(entity_id: str, brightness_pct: int | None = None, color_temp_kelvin: int | None = None, rgb_color: list[int] | None = None) -> str:
    """
    Turn on a light with optional brightness, color temperature, or RGB color.

    Args:
        entity_id: The light entity ID (e.g. 'light.living_room').
        brightness_pct: Brightness percentage 1-100.
        color_temp_kelvin: Color temperature in Kelvin (e.g. 2700 warm, 6500 cool).
        rgb_color: RGB color as [r, g, b] with values 0-255.
    """
    extra = {}
    if brightness_pct is not None:
        extra["brightness_pct"] = max(1, min(100, brightness_pct))
    if color_temp_kelvin is not None:
        extra["color_temp_kelvin"] = color_temp_kelvin
    if rgb_color is not None:
        extra["rgb_color"] = rgb_color
    return await call_ha_service("light", "turn_on", entity_id=entity_id, extra=extra if extra else None)

@tool
async def turn_off_light(entity_id: str) -> str:
    """
    Turn off a light.

    Args:
        entity_id: The light entity ID (e.g. 'light.living_room').
    """
    return await call_ha_service("light", "turn_off", entity_id=entity_id)

@tool
async def toggle_light(entity_id: str) -> str:
    """
    Toggle a light on/off.

    Args:
        entity_id: The light entity ID (e.g. 'light.living_room').
    """
    return await call_ha_service("light", "toggle", entity_id=entity_id)

@tool
async def set_light_brightness(entity_id: str, brightness_pct: int) -> str:
    """
    Set the brightness of a light.

    Args:
        entity_id: The light entity ID (e.g. 'light.living_room').
        brightness_pct: Brightness percentage 1-100.
    """
    return await call_ha_service("light", "turn_on", entity_id=entity_id, extra={"brightness_pct": max(1, min(100, brightness_pct))})

# ── Compatibility aliases for executor.py ────────────────────────────────────

# executor.py imports these exact names:
# get_entity_state, call_service, list_entities, scene_activate,
# media_play, media_pause, climate_set_temperature, cover_open, cover_close

@tool
async def get_entity_state(entity_id: str) -> str:
    """Get the current state and key attributes of a Home Assistant entity (alias for get_ha_entity_state)."""
    return await get_ha_entity_state(entity_id)

@tool
async def call_service(domain: str, service: str, entity_id: str | None = None, area_id: str | None = None, extra: dict | None = None) -> str:
    """Call any Home Assistant service (alias for call_ha_service)."""
    return await call_ha_service(domain, service, entity_id, area_id, extra)

@tool
async def list_entities(query: str, domain: str | None = None) -> str:
    """Search for Home Assistant entities by name or keyword (alias for search_ha_entities)."""
    return await search_ha_entities(query, domain)

@tool
async def scene_activate(entity_id: str) -> str:
    """Activate a Home Assistant scene."""
    return await call_ha_service("scene", "turn_on", entity_id=entity_id)

@tool
async def media_play(entity_id: str) -> str:
    """Play media on a media player."""
    return await call_ha_service("media_player", "media_play", entity_id=entity_id)

@tool
async def media_pause(entity_id: str) -> str:
    """Pause media on a media player."""
    return await call_ha_service("media_player", "media_pause", entity_id=entity_id)

@tool
async def climate_set_temperature(entity_id: str, temperature: float, hvac_mode: str | None = None) -> str:
    """Set climate temperature and optionally HVAC mode."""
    extra = {"temperature": temperature}
    if hvac_mode:
        extra["hvac_mode"] = hvac_mode
    return await call_ha_service("climate", "set_temperature", entity_id=entity_id, extra=extra)

@tool
async def cover_open(entity_id: str) -> str:
    """Open a cover."""
    return await call_ha_service("cover", "open_cover", entity_id=entity_id)

@tool
async def cover_close(entity_id: str) -> str:
    """Close a cover."""
    return await call_ha_service("cover", "close_cover", entity_id=entity_id)

# ── Core Tools ────────────────────────────────────────────────────────────────

@tool
async def call_ha_service(
    domain: str,
    service: str,
    entity_id: str | None = None,
    area_id: str | None = None,
    extra: dict | None = None,
) -> str:
    """
    Call any Home Assistant service to control devices or trigger automations.

    Use this for ALL device control: lights, switches, climate, covers,
    locks, media players, fans, vacuums, scripts, automations, etc.

    Args:
        domain:    HA service domain. Examples: 'light', 'switch', 'climate',
                   'cover', 'lock', 'media_player', 'fan', 'vacuum',
                   'automation', 'script', 'input_boolean'.
        service:   Service name within the domain. Examples: 'turn_on',
                   'turn_off', 'toggle', 'set_temperature', 'open_cover',
                   'lock', 'play_media', 'set_hvac_mode'.
        entity_id: Target entity ID (e.g. 'light.living_room',
                   'switch.patio', 'climate.bedroom'). Omit when targeting
                   an area or when the service takes no target.
        area_id:   Target area ID to affect all compatible entities in that
                   area (e.g. 'living_room', 'bedroom'). Use get_ha_areas
                   to discover area IDs.
        extra:     Additional service-call parameters as a dict.
                   Examples:
                     light.turn_on   → {'brightness_pct': 80, 'color_temp_kelvin': 3500}
                     climate.*       → {'temperature': 72, 'hvac_mode': 'cool'}
                     media_player.*  → {'volume_level': 0.5}
                     cover.*         → {'position': 50}

    Common patterns:
        Turn off a light:   domain='light', service='turn_off', entity_id='light.living_room'
        Dim a light to 50%: domain='light', service='turn_on', entity_id='light.kitchen',
                            extra={'brightness_pct': 50}
        Set thermostat:     domain='climate', service='set_temperature',
                            entity_id='climate.main', extra={'temperature': 72}
        Lock a door:        domain='lock', service='lock', entity_id='lock.front_door'
        Run a script:       domain='script', service='turn_on', entity_id='script.goodnight'
        Trigger automation: domain='automation', service='trigger',
                            entity_id='automation.welcome_home'
    """
    if not _HA_TOKEN:
        return "Error: HA_LONG_LIVED_TOKEN is not configured in the environment."

    payload: dict = {}
    if entity_id:
        payload["entity_id"] = entity_id
    if area_id:
        payload["area_id"] = area_id
    if extra:
        payload.update(extra)

    status, result = await _ha_post(f"/api/services/{domain}/{service}", payload)

    if status == 0:
        return f"Could not reach Home Assistant: {result}"
    if status == 401:
        return "Error: HA token is invalid or expired. Check HA_LONG_LIVED_TOKEN."
    if status == 404:
        return (
            f"Service '{domain}.{service}' not found in Home Assistant. "
            "Use get_ha_entity_state or search_ha_entities to verify the domain/service."
        )
    if status not in (200, 201):
        return f"Home Assistant returned HTTP {status}: {result}"

    # result is a list of state dicts for affected entities
    if isinstance(result, list) and result:
        affected = [s.get("entity_id", "?") for s in result]
        states   = [s.get("state", "?") for s in result]
        pairs    = ", ".join(f"{e}={s}" for e, s in zip(affected, states))
        return f"Done. Affected entities → {pairs}"

    target_desc = entity_id or area_id or "(no target)"
    return f"Service {domain}.{service} called on {target_desc}. (No state change reported.)"

@tool
async def get_ha_entity_state(entity_id: str) -> str:
    """
    Get the current state and key attributes of a Home Assistant entity.

    Use this to check whether a device is on/off, get temperature readings,
    brightness levels, lock status, battery levels, sensor values, etc.
    before deciding what action to take.

    Args:
        entity_id: The full entity ID (e.g. 'light.living_room',
                   'sensor.bedroom_temperature', 'lock.front_door').

    Returns a summary of state + the most relevant attributes.
    """
    if not _HA_TOKEN:
        return "Error: HA_LONG_LIVED_TOKEN is not configured."

    status, data = await _ha_get(f"/api/states/{entity_id}")

    if status == 0:
        return f"Could not reach Home Assistant: {data}"
    if status == 404:
        return (
            f"Entity '{entity_id}' not found. "
            "Use search_ha_entities to find the correct entity ID."
        )
    if status != 200:
        return f"Home Assistant returned HTTP {status}: {data}"

    state = data.get("state", "unknown")
    attrs = data.get("attributes", {})

    # Build a concise summary — surface the most useful attributes
    summary_parts = [f"state={state}"]
    for key in (
        "friendly_name", "brightness", "color_temp_kelvin",
        "current_temperature", "temperature", "hvac_mode", "hvac_action",
        "volume_level", "media_title", "battery_level",
        "position", "is_volume_muted", "device_class",
    ):
        if key in attrs:
            summary_parts.append(f"{key}={attrs[key]}")

    return f"{entity_id}: " + "  |  ".join(summary_parts)

@tool
async def search_ha_entities(query: str, domain: str | None = None) -> str:
    """
    Search for Home Assistant entities by name or keyword.

    Use this when you need to find the correct entity_id before calling
    call_ha_service or get_ha_entity_state — especially when the user says
    something like 'living room lights' and you need the actual entity IDs.

    Args:
        query:  Name fragment to search for (e.g. 'living room', 'kitchen',
                'thermostat', 'front door').
        domain: Optional domain filter to narrow results (e.g. 'light',
                'switch', 'climate', 'lock', 'sensor', 'binary_sensor',
                'cover', 'media_player', 'fan', 'vacuum', 'automation').

    Returns a list of matching entity IDs with their current states and
    friendly names, suitable for use in subsequent tool calls.
    """
    if not _HA_TOKEN:
        return "Error: HA_LONG_LIVED_TOKEN is not configured."

    status, states = await _ha_get("/api/states", timeout=15)
    if status == 0:
        return f"Could not reach Home Assistant: {states}"
    if status != 200:
        return f"Home Assistant returned HTTP {status}: {states}"

    if not isinstance(states, list):
        return "Unexpected response from Home Assistant states endpoint."

    query_lower = query.lower()
    matches = []

    for entity in states:
        eid = entity.get("entity_id", "")
        name = entity.get("attributes", {}).get("friendly_name", "")
        state = entity.get("state", "")

        # Domain filter
        if domain and not eid.startswith(f"{domain}."):
            continue

        # Name/ID match
        if query_lower in eid.lower() or query_lower in name.lower():
            matches.append(f"  {eid}  (name='{name}', state={state})")

    if not matches:
        domain_hint = f" in domain '{domain}'" if domain else ""
        return f"No entities found matching '{query}'{domain_hint}."

    if len(matches) > 25:
        matches = matches[:25]
        matches.append(f"  ... (truncated — refine your query or add a domain filter)")

    return f"Entities matching '{query}':\n" + "\n".join(matches)

@tool
async def get_ha_areas() -> str:
    """
    List all areas (rooms) defined in Home Assistant.

    Use this to discover area IDs when the user refers to a room by name
    (e.g. 'living room', 'bedroom', 'kitchen') so you can pass the correct
    area_id to call_ha_service.

    Returns a list of area IDs and their display names.
    """
    if not _HA_TOKEN:
        return "Error: HA_LONG_LIVED_TOKEN is not configured."

    # Use template engine to query area registry
    template = (
        "{% set ns = namespace(areas=[]) %}"
        "{% for area in areas() %}"
        "{% set ns.areas = ns.areas + [{'id': area, 'name': area_name(area)}] %}"
        "{% endfor %}"
        "{{ ns.areas | tojson }}"
    )
    t_status, t_result = await _ha_post("/api/template", {"template": template})

    if t_status == 200 and isinstance(t_result, str):
        try:
            area_list = json.loads(t_result)
            if area_list:
                lines = [f"  {a['id']}  →  {a['name']}" for a in area_list]
                return "Home Assistant areas:\n" + "\n".join(lines)
        except (json.JSONDecodeError, KeyError):
            pass

    # Fallback: extract area info from entity attributes where present
    return (
        "Could not retrieve area list from registry. "
        "Use search_ha_entities with a room name to find entities instead, "
        "or try area IDs like 'living_room', 'bedroom', 'kitchen' directly."
    )

@tool
async def fire_ha_event(event_type: str, event_data: dict | None = None) -> str:
    """
    Fire a custom event on the Home Assistant event bus.

    Use for triggering automations that listen for specific events,
    sending notifications through HA's notification system, or
    interacting with integrations that use event-based triggers.

    Args:
        event_type: The event type to fire (e.g. 'jarvis_command',
                    'custom_notification', 'my_integration_trigger').
        event_data: Optional payload dict to attach to the event.
    """
    if not _HA_TOKEN:
        return "Error: HA_LONG_LIVED_TOKEN is not configured."

    payload = event_data or {}
    status, result = await _ha_post(f"/api/events/{event_type}", payload)

    if status == 0:
        return f"Could not reach Home Assistant: {result}"
    if status not in (200, 201):
        return f"Home Assistant returned HTTP {status} for event '{event_type}': {result}"

    return f"Event '{event_type}' fired successfully."

# ── Harness registry ─────────────────────────────────────────────────────────
# get_all_harness_tools() is the single import point for executor.py.
# To add a new harness (e.g. Plex, Unraid, Proxmox):
#   1. Create core/<name>_tools.py with @tool functions.
#   2. Import them here and append to the list below.

def get_all_harness_tools() -> list:
    """Return all registered harness tools for the executor."""
    return [
        call_ha_service,
        get_ha_entity_state,
        search_ha_entities,
        get_ha_areas,
        fire_ha_event,
        turn_on_light,
        turn_off_light,
        toggle_light,
        set_light_brightness,
        # Compatibility aliases for executor.py
        get_entity_state,
        call_service,
        list_entities,
        scene_activate,
        media_play,
        media_pause,
        climate_set_temperature,
        cover_open,
        cover_close,
    ]

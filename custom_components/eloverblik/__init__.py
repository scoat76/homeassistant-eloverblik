"""The Eloverblik integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .normalize import normalize_entry_data
from .coordinator import EloverblikDataUpdateCoordinator
from .data import HassEloverblik

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Eloverblik component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Eloverblik from a config entry."""
    raw = dict(entry.data)
    data = normalize_entry_data(raw)
    if data != raw:
        hass.config_entries.async_update_entry(entry, data=data)

    refresh_token = data["refresh_token"]
    metering_point = data["metering_point"]

    hass_eloverblik = HassEloverblik(refresh_token, metering_point)
    coordinator = EloverblikDataUpdateCoordinator(hass, entry, hass_eloverblik)

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "hass_eloverblik": hass_eloverblik,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Diagnostik til UI (download diagnostics)."""
    info = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not info:
        return {"error": "Ingen aktiv integration for denne post."}

    coordinator: EloverblikDataUpdateCoordinator = info["coordinator"]
    he: HassEloverblik = info["hass_eloverblik"]

    last_exc = getattr(coordinator, "last_exception", None)

    return {
        "metering_point": entry.data.get("metering_point"),
        "last_update_success": coordinator.last_update_success,
        "last_exception": repr(last_exc) if last_exc else None,
        "statistic_last_error": coordinator.statistic_last_error,
        "statistic_last_success": coordinator.statistic_last_success.isoformat()
        if coordinator.statistic_last_success
        else None,
        "last_data_warnings": coordinator.data.get("warnings") if coordinator.data else [],
        "day_data_date": he.get_data_date(),
    }

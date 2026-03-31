"""Diagnostics for Eloverblik config entries."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import EloverblikDataUpdateCoordinator
from .data import HassEloverblik


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    info = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not info:
        return {"error": "Integration not loaded for this entry."}

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

"""Data update coordinator for Eloverblik."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import requests
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import MIN_TIME_BETWEEN_UPDATES
from .data import HassEloverblik

_LOGGER = logging.getLogger(__name__)


class EloverblikDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll consumption, tariffs, meter reading; expose status for UI."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        hass_eloverblik: HassEloverblik,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"Eloverblik {hass_eloverblik.get_metering_point()}",
            update_interval=MIN_TIME_BETWEEN_UPDATES,
            config_entry=entry,
        )
        self.hass_eloverblik = hass_eloverblik
        self.statistic_last_error: str | None = None
        self.statistic_last_success: datetime | None = None
        self._last_poll_http_status: int | None = None

    async def _async_update_data(self) -> dict[str, Any]:
        def refresh() -> dict[str, Any]:
            return self.hass_eloverblik.refresh_all()

        try:
            result = await self.hass.async_add_executor_job(refresh)
        except requests.HTTPError as err:
            code = err.response.status_code if err.response is not None else None
            self._last_poll_http_status = code
            if code == 401:
                raise UpdateFailed("Invalid or expired refresh token (401).") from err
            if code == 429:
                raise UpdateFailed("Too many requests to Eloverblik (429). Wait and retry.") from err
            if code == 503:
                raise UpdateFailed("DataHub / Eloverblik temporarily unavailable (503).") from err
            raise UpdateFailed(f"HTTP error from Eloverblik: {err}") from err
        except requests.RequestException as err:
            self._last_poll_http_status = None
            raise UpdateFailed(f"Cannot reach Eloverblik: {err}") from err

        self._last_poll_http_status = result.get("http_status")
        if result.get("critical_message"):
            raise UpdateFailed(result["critical_message"])
        return result

    def set_statistic_error(self, message: str | None) -> None:
        """Called from statistic entity when import fails."""
        self.statistic_last_error = message
        self.async_update_listeners()

    def set_statistic_success(self, when: datetime) -> None:
        """Called when statistic import succeeds."""
        self.statistic_last_error = None
        self.statistic_last_success = when
        self.async_update_listeners()

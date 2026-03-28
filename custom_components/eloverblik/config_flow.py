"""Config flow for Eloverblik integration."""
from __future__ import annotations

import logging

import requests
import voluptuous as vol
from requests import HTTPError

from homeassistant import config_entries, core, exceptions
from pyeloverblik.eloverblik import Eloverblik

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required("refresh_token"): str,
        vol.Required("metering_point"): str,
    }
)


def _validate_latest_sync(token: str, metering_point: str) -> None:
    """Kald kun fra executor. Kaster ved ugyldig auth eller API-fejl."""
    client = Eloverblik(token)
    latest = client.get_latest(metering_point)
    if latest.status == 200:
        return
    if latest.status in (401, 403):
        raise InvalidAuth()
    if latest.status == 429:
        raise RateLimited()
    if latest.status == 503:
        raise DatahubUnavailable()
    raise CannotConnect()


async def validate_input(hass: core.HomeAssistant, data: dict) -> dict:
    """Validate the user input allows us to connect."""
    token = data["refresh_token"]
    metering_point = data["metering_point"]

    try:
        await hass.async_add_executor_job(_validate_latest_sync, token, metering_point)
    except HTTPError as err:
        code = err.response.status_code if err.response is not None else None
        if code in (401, 403):
            raise InvalidAuth() from err
        if code == 429:
            raise RateLimited() from err
        if code == 503:
            raise DatahubUnavailable() from err
        raise CannotConnect() from err
    except requests.RequestException as err:
        raise CannotConnect() from err

    return {"title": f"Eloverblik {metering_point}"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Eloverblik."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                metering_point = user_input["metering_point"]
                await self.async_set_unique_id(metering_point)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except RateLimited:
                errors["base"] = "rate_limited"
            except DatahubUnavailable:
                errors["base"] = "datahub_unavailable"
            except exceptions.HomeAssistantError:
                raise
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""


class RateLimited(exceptions.HomeAssistantError):
    """Too many requests (429)."""


class DatahubUnavailable(exceptions.HomeAssistantError):
    """DataHub / API temporarily unavailable (503)."""

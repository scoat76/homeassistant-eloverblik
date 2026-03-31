"""Eloverblik API client wrapper (synkron, kaldes via executor)."""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from typing import Any

import requests
from pyeloverblik.eloverblik import Eloverblik
from pyeloverblik.models import TimeSeries

_LOGGER = logging.getLogger(__name__)


class HassEloverblik:
    """Holder målepunkt, cache af seneste API-svar og ren fetch-logik."""

    def __init__(self, refresh_token: str, metering_point: str) -> None:
        self._client = Eloverblik(refresh_token)
        self._metering_point = metering_point
        self._day_data = None
        self._year_data = None
        self._tariff_data = None
        self._meter_reading_data = None

    def get_total_day(self):
        if self._day_data is not None:
            return round(self._day_data.get_total_metering_data(), 3)
        return None

    def get_total_year(self):
        if self._year_data is not None:
            return round(self._year_data.get_total_metering_data(), 3)
        return None

    def get_usage_hour(self, hour):
        if self._day_data is not None:
            try:
                return round(self._day_data.get_metering_data(hour), 3)
            except IndexError:
                self._day_data.get_metering_data(23)
                _LOGGER.info(
                    "Unable to get data for hour %s. "
                    "If switch to daylight saving day this is not an error.",
                    hour,
                )
                return 0
        return None

    def get_hourly_data(
        self, from_date: datetime, to_date: datetime
    ) -> dict[datetime, TimeSeries] | None:
        """Time series til langtidsstatistik (ingen throttling her)."""
        try:
            raw_data = self._client.get_time_series(
                self._metering_point, from_date, to_date
            )
            if raw_data.status == 200:
                json_response = json.loads(raw_data.body)
                return self._client._parse_result(json_response)
            _LOGGER.warning(
                "Error from eloverblik while getting historic data: %s - %s",
                raw_data.status,
                raw_data.body,
            )
        except requests.exceptions.HTTPError:
            e = sys.exc_info()[1]
            _LOGGER.warning("HTTP error while getting historic data: %s", e)
        except Exception:
            e = sys.exc_info()[1]
            _LOGGER.warning("Exception while getting historic data: %s", e)
        return None

    def get_data_date(self):
        if self._day_data is not None:
            return self._day_data.data_date.date().strftime("%Y-%m-%d")
        return None

    def get_metering_point(self):
        return self._metering_point

    def get_tariff_sum_hour(self, hour):
        if self._tariff_data is not None:
            total = 0.0
            for tariff in self._tariff_data.charges.values():
                if isinstance(tariff, list):
                    if len(tariff) == 24:
                        total += tariff[hour - 1]
                    else:
                        _LOGGER.warning(
                            "Unexpected length of tariff array (%s), expected 24.",
                            len(tariff),
                        )
                else:
                    total += float(tariff)
            return total
        return None

    def meter_reading_date(self):
        if self._meter_reading_data is not None:
            return self._meter_reading_data.reading_date
        return None

    def meter_reading(self):
        if self._meter_reading_data is not None:
            return self._meter_reading_data.reading
        return None

    def refresh_all(self) -> dict[str, Any]:
        """
        Hent forbrug, år, tariffer og måleraflæsning.

        Returnerer metadata til coordinator; kaster ikke (undtagen requests
        fra token-endpoint, som kan rejse HTTPError).
        """
        warnings: list[str] = []
        http_status: int | None = None

        _LOGGER.debug("Fetching energy data from Eloverblik")
        try:
            day_data = self._client.get_latest(self._metering_point)
            http_status = getattr(day_data, "status", None)
            if day_data.status == 200:
                self._day_data = day_data
            else:
                warnings.append(f"day_data:{day_data.status}")
                if day_data.status in (401, 403):
                    return {
                        "warnings": warnings,
                        "http_status": day_data.status,
                        "critical_message": (
                            f"Eloverblik rejected consumption data ({day_data.status}). "
                            "Check refresh token and metering point."
                        ),
                    }

            year_data = self._client.get_per_month(self._metering_point)
            if year_data.status == 200:
                self._year_data = year_data
            else:
                warnings.append(f"year_data:{year_data.status}")
        except requests.exceptions.HTTPError:
            raise
        except Exception:
            e = sys.exc_info()[1]
            _LOGGER.warning("Exception while fetching energy: %s", e)
            warnings.append(str(e))

        _LOGGER.debug("Fetching tariff data from Eloverblik")
        try:
            tariff_data = self._client.get_tariffs(self._metering_point)
            if tariff_data.status == 200:
                self._tariff_data = tariff_data
            else:
                warnings.append(f"tariff:{tariff_data.status}")
        except requests.exceptions.HTTPError:
            raise
        except Exception:
            e = sys.exc_info()[1]
            _LOGGER.warning("Exception while fetching tariffs: %s", e)
            warnings.append(str(e))

        _LOGGER.debug("Fetching meter reading data from Eloverblik")
        try:
            meter_reading_data = self._client.get_meter_reading_latest(
                self._metering_point
            )
            if meter_reading_data.status == 200:
                self._meter_reading_data = meter_reading_data
            else:
                _LOGGER.info(
                    "Meter reading not available (%s): %s",
                    meter_reading_data.status,
                    meter_reading_data.detailed_status,
                )
        except requests.exceptions.HTTPError:
            raise
        except Exception:
            e = sys.exc_info()[1]
            _LOGGER.warning("Exception while fetching meter reading: %s", e)

        if self._day_data is None:
            return {
                "warnings": warnings,
                "http_status": http_status,
                "critical_message": (
                    "Could not fetch daily consumption from Eloverblik. "
                    "Check token, metering point, and whether data exists at the grid operator."
                ),
            }

        return {
            "warnings": warnings,
            "http_status": http_status,
            "metering_point": self._metering_point,
        }

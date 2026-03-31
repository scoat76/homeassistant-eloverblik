"""Platform for Eloverblik sensor integration."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import (
    DOMAIN as RECORDER_DOMAIN,
    async_import_statistics,
    get_last_statistics,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from pyeloverblik.models import TimeSeries

from .const import CURRENCY_KRONER_PER_KILO_WATT_HOUR, DOMAIN
from .coordinator import EloverblikDataUpdateCoordinator
from .data import HassEloverblik

_LOGGER = logging.getLogger(__name__)

_STATISTIC_MIN_INTERVAL = timedelta(minutes=60)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the sensor platform."""
    domain_data = hass.data[DOMAIN][entry.entry_id]
    coordinator: EloverblikDataUpdateCoordinator = domain_data["coordinator"]
    hass_eloverblik: HassEloverblik = domain_data["hass_eloverblik"]

    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.unique_id)},
        name=f"Eloverblik {entry.data['metering_point']}",
        manufacturer="Eloverblik",
        configuration_url="https://eloverblik.dk",
    )

    sensors: list[SensorEntity] = [
        EloverblikEnergy(
            "Eloverblik Energy Total", "total", coordinator, device_info
        ),
        EloverblikEnergy(
            "Eloverblik Energy Total (Year)", "year_total", coordinator, device_info
        ),
        MeterReading("Eloverblik Meter Reading", coordinator, device_info),
    ]
    for hour in range(1, 25):
        sensors.append(
            EloverblikEnergy(
                f"Eloverblik Energy {hour - 1}-{hour}",
                "hour",
                coordinator,
                device_info,
                hour,
            )
        )
    sensors.append(EloverblikTariff("Eloverblik Tariff Sum", coordinator, device_info))
    sensors.append(EloverblikApiStatusSensor(coordinator, device_info))
    sensors.append(
        EloverblikStatistic(coordinator, hass_eloverblik, device_info),
    )

    async_add_entities(sensors)


class EloverblikEnergy(CoordinatorEntity[EloverblikDataUpdateCoordinator], SensorEntity):
    """Representation of an energy sensor."""

    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(
        self,
        name: str,
        sensor_type: str,
        coordinator: EloverblikDataUpdateCoordinator,
        device_info: DeviceInfo,
        hour: int | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._sensor_type = sensor_type
        self._hour = hour
        self._attr_name = name
        self._attr_device_info = device_info
        mp = coordinator.hass_eloverblik.get_metering_point()
        if sensor_type == "hour":
            self._attr_unique_id = f"{mp}-{hour}"
        elif sensor_type == "total":
            self._attr_unique_id = f"{mp}-total"
        elif sensor_type == "year_total":
            self._attr_unique_id = f"{mp}-year-total"
        else:
            raise ValueError(f"Unexpected sensor_type: {sensor_type}.")

    @property
    def native_value(self) -> float | None:
        he = self.coordinator.hass_eloverblik
        if self._sensor_type == "hour":
            return he.get_usage_hour(self._hour)
        if self._sensor_type == "total":
            return he.get_total_day()
        if self._sensor_type == "year_total":
            return he.get_total_year()
        raise ValueError(f"Unexpected sensor_type: {self._sensor_type}.")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        he = self.coordinator.hass_eloverblik
        data_date = he.get_data_date()
        return {
            "Metering date": data_date,
            "metering_date": data_date,
        }


class MeterReading(CoordinatorEntity[EloverblikDataUpdateCoordinator], SensorEntity):
    """Representation of a meter reading sensor."""

    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(
        self,
        name: str,
        coordinator: EloverblikDataUpdateCoordinator,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_device_info = device_info
        self._attr_unique_id = (
            f"{coordinator.hass_eloverblik.get_metering_point()}-meter-reading"
        )

    @property
    def native_value(self) -> float | str | None:
        return self.coordinator.hass_eloverblik.meter_reading()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "meter_reading_date": self.coordinator.hass_eloverblik.meter_reading_date(),
        }


class EloverblikTariff(CoordinatorEntity[EloverblikDataUpdateCoordinator], SensorEntity):
    """Hourly tariff sum from Eloverblik."""

    def __init__(
        self,
        name: str,
        coordinator: EloverblikDataUpdateCoordinator,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_device_info = device_info
        self._attr_unique_id = (
            f"{coordinator.hass_eloverblik.get_metering_point()}-tariff-sum"
        )
        self._attr_native_unit_of_measurement = CURRENCY_KRONER_PER_KILO_WATT_HOUR

    @property
    def native_value(self) -> float | None:
        he = self.coordinator.hass_eloverblik
        hour_idx = dt_util.now().hour
        return he.get_tariff_sum_hour(hour_idx + 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        he = self.coordinator.hass_eloverblik
        hourly = [he.get_tariff_sum_hour(h) for h in range(1, 25)]
        return {"hourly": hourly}


class EloverblikApiStatusSensor(
    CoordinatorEntity[EloverblikDataUpdateCoordinator], SensorEntity
):
    """Human-readable API / poll status without reading logs."""

    _attr_icon = "mdi:cloud-check-outline"
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: EloverblikDataUpdateCoordinator,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator)
        self._attr_name = "Eloverblik API status"
        self._attr_device_info = device_info
        self._attr_unique_id = (
            f"{coordinator.hass_eloverblik.get_metering_point()}-api-status"
        )

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> str:
        if not self.coordinator.last_update_success:
            exc = getattr(self.coordinator, "last_exception", None)
            if exc:
                return f"Error: {exc}"
            return "Error: last update failed"
        if self.coordinator.statistic_last_error:
            return f"OK (statistics: {self.coordinator.statistic_last_error})"
        return "OK"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        c = self.coordinator
        data = c.data or {}
        return {
            "last_statistic_success": c.statistic_last_success.isoformat()
            if c.statistic_last_success
            else None,
            "last_statistic_error": c.statistic_last_error,
            "poll_warnings": data.get("warnings", []),
        }


class EloverblikStatistic(SensorEntity):
    """Import hourly use into long-term statistics / energy dashboard."""

    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_value = None
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: EloverblikDataUpdateCoordinator,
        hass_eloverblik: HassEloverblik,
        device_info: DeviceInfo,
    ) -> None:
        self._coordinator = coordinator
        self._hass_eloverblik = hass_eloverblik
        self._attr_name = "Eloverblik Energy Statistic"
        self._attr_unique_id = f"{hass_eloverblik.get_metering_point()}-statistic"
        self._attr_device_info = device_info
        self._last_full_update_attempt: datetime | None = None

    @property
    def available(self) -> bool:
        return True

    def _on_coordinator_update(self) -> None:
        """Re-try statistic import when the data coordinator refreshes."""
        self.hass.async_create_task(self.async_update())

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self._coordinator.async_add_listener(self._on_coordinator_update)
        )
        self.hass.async_create_task(self.async_update())

    async def async_will_remove_from_hass(self) -> None:
        await get_instance(self.hass).async_clear_statistics([self.entity_id])
        await super().async_will_remove_from_hass()

    async def async_update(self) -> None:
        """Update history when enough time has passed and new data may exist."""
        now = datetime.now(timezone.utc)
        last_stat = await self._get_last_stat(self.hass)
        if last_stat is not None:
            last_start = datetime.fromtimestamp(
                last_stat["start"], tz=timezone.utc
            )
            if now - last_start < timedelta(days=1):
                return

        if self._last_full_update_attempt is not None:
            if now - self._last_full_update_attempt < _STATISTIC_MIN_INTERVAL:
                return
        self._last_full_update_attempt = now

        await self._update_data(last_stat)

    async def _update_data(self, last_stat: dict[str, Any] | None) -> None:
        if last_stat is None:
            from_date = datetime(datetime.now().year - 1, 1, 1)
        else:
            last_start = datetime.fromtimestamp(
                last_stat["start"], tz=timezone.utc
            )
            from_date = last_start + timedelta(hours=13)

        data = await self.hass.async_add_executor_job(
            self._hass_eloverblik.get_hourly_data,
            from_date,
            datetime.now(),
        )

        if data is None:
            msg = "No time series data from Eloverblik (see log for details)."
            self._coordinator.set_statistic_error(msg)
            _LOGGER.debug("No hourly data returned from Eloverblik for statistics")
            return

        inserted = await self._insert_statistics(data, last_stat)
        self._coordinator.set_statistic_success(datetime.now(timezone.utc))
        if inserted == 0:
            _LOGGER.debug("No new statistic points to import (data may be up to date)")

    async def _insert_statistics(
        self,
        data: dict[datetime, TimeSeries],
        last_stat: dict[str, Any] | None,
    ) -> int:
        statistics: list[StatisticData] = []

        if last_stat is not None:
            total = last_stat["sum"]
        else:
            total = 0

        sorted_time_series = sorted(
            data.values(), key=lambda timeseries: timeseries.data_date
        )

        for time_series in sorted_time_series:
            if time_series._metering_data is not None:
                number_of_hours = len(time_series._metering_data)
                date = time_series.data_date - timedelta(hours=number_of_hours)

                for hour in range(0, number_of_hours):
                    start = date + timedelta(hours=hour)
                    total += time_series.get_metering_data(hour + 1)
                    statistics.append(StatisticData(start=start, sum=total))

        metadata = StatisticMetaData(
            name=self._attr_name,
            source=RECORDER_DOMAIN,
            statistic_id=self.entity_id,
            unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            has_mean=False,
            has_sum=True,
        )

        if len(statistics) > 0:
            await async_import_statistics(self.hass, metadata, statistics)
        return len(statistics)

    async def _get_last_stat(
        self, hass: HomeAssistant
    ) -> dict[str, Any] | None:
        last_stats = await get_instance(hass).async_add_executor_job(
            get_last_statistics, hass, 1, self.entity_id, True, {"sum"}
        )

        if self.entity_id in last_stats and len(last_stats[self.entity_id]) > 0:
            return last_stats[self.entity_id][0]
        return None

# Eloverblik Home Assistant Component - Codebase Inventory & Analysis

## Overview
The `eloverblik` custom component integrates the [eloverblik.dk](https://eloverblik.dk) API into Home Assistant. It pulls electricity consumption data, tariffs, and meter readings for Danish energy consumers.

This documentation serves as an inventory of the codebase and its architecture to provide full context to future AI agents or developers.

## File Structure (`custom_components/eloverblik/`)
*   `__init__.py`: Core component setup. It manages the `HassEloverblik` object that interfaces with the external API, handles throttling (60-minute limits), error logging, and API data caching.
*   `sensor.py`: Home Assistant entity definitions. Defines several Sensor and SensorEntity classes that wrap data pulled in `__init__.py`.
*   `config_flow.py`: Implements the UI configuration flow in Home Assistant (`ConfigFlow`). Validates the refresh token and metering point.
*   `const.py`: Contains constants like the integration `DOMAIN` ("eloverblik") and `CURRENCY_KRONER_PER_KILO_WATT_HOUR`.
*   `manifest.json`: Home Assistant integration manifest. Defines the integration version, dependencies (e.g., `pyeloverblik==0.4.4`), and domain.
*   `strings.json` & `translations/`: Localization files for the Home Assistant UI configuration flow.

## External Dependencies
*   **pyeloverblik (v0.4.4):** This is the underlying Python library used to communicate with the Eloverblik API. The integration imports `Eloverblik` client and `TimeSeries` models from this package.
*   **voluptuous:** Used for schema validation in `config_flow.py`.

## Core Mechanisms
1.  **Authentication & Configuration:**
    *   Setup uses UI-based Config Flow.
    *   Requires a `refresh_token` (from eloverblik.dk) and a `metering_point` (the ID of the electricity meter).
    *   The Config Flow uses `async_step_user` to validate the connection by attempting to fetch tariffs for the given metering point before saving the entry.
2.  **API Data Fetching (`__init__.py` -> `HassEloverblik`):**
    *   The `HassEloverblik` class encapsulates all calls to `pyeloverblik.Eloverblik`.
    *   Data updates are strictly throttled using Home Assistant's `@Throttle(MIN_TIME_BETWEEN_UPDATES)` decorator, where `MIN_TIME_BETWEEN_UPDATES` is set to 60 minutes.
    *   Fetch methods include: `update_energy()`, `update_tariffs()`, and `update_meter_reading()`. Historic data fetching is handled via `get_hourly_data()`.
3.  **Sensor Entities (`sensor.py`):**
    The component exposes multiple sensors per metering point:
    *   `EloverblikEnergy`: Creates total, yearly total, and 24 individual hourly energy sensors.
    *   `MeterReading`: Provides the latest available meter reading.
    *   `EloverblikTariff`: Provides the tariff sum for the current hour, with upcoming hourly tariffs stored in extra state attributes.
    *   `EloverblikStatistic`: Injects historical data directly into Home Assistant's Long Term Statistics (`async_import_statistics`). This is critical for the HA Energy Dashboard.

## Notes for Future AI Agents
*   **Data Availability Delay:** The Eloverblik API usually delays providing electricity data by 1 to 2 days. The code contains logic (e.g., in `EloverblikStatistic._update_data`) to handle these expected data gaps.
*   **Throttling is Crucial:** The Eloverblik API is notoriously slow and rate-limited. Removing or reducing the `@Throttle(timedelta(minutes=60))` in `__init__.py` will likely lead to API bans or unstable Home Assistant performance.
*   **Long Term Statistics:** The `EloverblikStatistic` relies heavily on `recorder` integration functionality (`async_import_statistics` and `get_last_statistics`). Modifications here must adhere to HA's strict Long Term Statistics guidelines to avoid database corruption or duplicate data points.
*   **Fork Status:** This repository is an imported copy (fork) of the original `JonasPed/homeassistant-eloverblik`, which is no longer actively maintained by its creator. Future development should occur within this repository.

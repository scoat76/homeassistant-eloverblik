# Integrating Eloverblik with Home Assistant Energy Dashboard

The Eloverblik custom component provides **Long Term Statistics**, making it fully compatible with the native Home Assistant Energy Dashboard. This allows you to track, analyze, and compare your energy consumption over months and years.

Follow these steps to set it up:

## Prerequisites
* The Eloverblik integration must be installed and fully configured with a valid `refresh_token` and `metering_point`.
* Allow the integration some time (up to 1 hour) to perform its initial data pull from the Eloverblik API and populate Home Assistant's statistics database.

## Step-by-Step Configuration

1. **Open Energy Dashboard Settings:**
   * In your Home Assistant sidebar, go to **Settings**.
   * Click on **Dashboards**.
   * Select **Energy**.

2. **Add Grid Consumption:**
   * In the **Electricity grid** section, under *Grid consumption*, click the **Add consumption** button.
   * A dialog will appear asking you to choose a sensor.
   * Search for and select the **Eloverblik Energy Statistic** sensor. It usually has an entity ID like `sensor.<your_metering_point>_statistic`.

   *(Optional: If your electricity provider uses tariffs or dynamic pricing, you can configure the pricing in this dialog using either a static price or another sensor).*

3. **Save and Wait:**
   * Click **Save**.
   * **Important:** Home Assistant processes energy statistics periodically (usually once an hour). Your charts will be completely empty at first. **Wait 1-2 hours** for the data to be processed and displayed on the Energy dashboard.

## Important Notes on Eloverblik Data
* **Data Delay:** The Eloverblik API does not provide real-time data. Data for today is usually not available until tomorrow or the day after. Because of this, your Energy Dashboard will always be updated retroactively. "Today" will generally show 0 kWh, but the previous days will populate accurately as the API provides the data.
* **Historical Import:** When you first set up the integration, it attempts to download and inject your historical data (typically from January 1st of the previous year) directly into Home Assistant's statistics database.

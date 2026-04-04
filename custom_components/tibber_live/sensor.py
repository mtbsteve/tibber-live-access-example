"""Sensor platform for Tibber Live integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TibberLiveData
from .const import DOMAIN, LIVE_SENSOR_TYPES, PRICE_SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)

# Map API field names → sensor keys
MEASUREMENT_MAP = {
    "power": "power",
    "minPower": "min_power",
    "averagePower": "average_power",
    "maxPower": "max_power",
    "accumulatedConsumption": "accumulated_consumption",
    "accumulatedCost": "accumulated_cost",
    "powerProduction": "power_production",
    "accumulatedProduction": "accumulated_production",
    "lastMeterProduction": "last_meter_production",
    "lastMeterConsumption": "last_meter_consumption",
}

DEVICE_CLASS_MAP = {
    "power": SensorDeviceClass.POWER,
    "energy": SensorDeviceClass.ENERGY,
    "monetary": SensorDeviceClass.MONETARY,
}

STATE_CLASS_MAP = {
    "measurement": SensorStateClass.MEASUREMENT,
    "total_increasing": SensorStateClass.TOTAL_INCREASING,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tibber Live sensors from a config entry."""
    runtime: TibberLiveData = hass.data[DOMAIN][entry.entry_id]
    client = runtime.client
    entities: list[SensorEntity] = []

    for home in runtime.homes:
        home_id = home["id"]
        addr = home["address"]
        home_label = f"{addr['address1']}, {addr['city']}"

        device_info = DeviceInfo(
            identifiers={(DOMAIN, home_id)},
            name=f"Tibber {home_label}",
            manufacturer="Tibber",
            model="Pulse / Watty",
        )

        # Live measurement sensors
        for sensor_key, sensor_def in LIVE_SENSOR_TYPES.items():
            entities.append(
                TibberLiveSensor(
                    home_id=home_id,
                    sensor_key=sensor_key,
                    sensor_def=sensor_def,
                    device_info=device_info,
                    entry_id=entry.entry_id,
                )
            )

        # Price sensors
        for sensor_key, sensor_def in PRICE_SENSOR_TYPES.items():
            entities.append(
                TibberPriceSensor(
                    home_id=home_id,
                    sensor_key=sensor_key,
                    sensor_def=sensor_def,
                    device_info=device_info,
                    entry_id=entry.entry_id,
                    runtime=runtime,
                )
            )

    async_add_entities(entities)

    # Subscribe to live WebSocket data for each home
    for home in runtime.homes:
        home_id = home["id"]

        # Find the live sensors for this home
        home_live_sensors: dict[str, TibberLiveSensor] = {
            e.sensor_key: e  # type: ignore[attr-defined]
            for e in entities
            if isinstance(e, TibberLiveSensor) and e.home_id == home_id  # type: ignore[attr-defined]
        }

        async def make_callback(sensors: dict[str, TibberLiveSensor]):
            """Create a closure for the callback."""
            async def on_measurement(data: dict[str, Any]) -> None:
                currency = data.get("currency", "")
                for api_key, sensor_key in MEASUREMENT_MAP.items():
                    sensor = sensors.get(sensor_key)
                    if sensor is None:
                        continue

                    value = data.get(api_key)

                    # Clamp negative production to zero
                    if sensor_key == "last_meter_production" and value is not None:
                        value = max(value, 0)

                    # Set currency unit for monetary sensors
                    if sensor_key == "accumulated_cost" and currency:
                        sensor.set_currency(currency)

                    sensor.update_value(value)

            return on_measurement

        cb = await make_callback(home_live_sensors)
        unsub = await client.async_subscribe_live(home_id, cb)
        runtime.unsubscribes.append(unsub)


class TibberLiveSensor(SensorEntity):
    """Sensor for a single Tibber live measurement field."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        home_id: str,
        sensor_key: str,
        sensor_def: dict[str, Any],
        device_info: DeviceInfo,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        self._home_id = home_id
        self._sensor_key = sensor_key
        self._attr_name = sensor_def["name"]
        self._attr_unique_id = f"{home_id}_{sensor_key}"
        self._attr_icon = sensor_def.get("icon")
        self._attr_device_info = device_info
        self._attr_native_value = None

        # Device class
        dc = sensor_def.get("device_class")
        self._attr_device_class = DEVICE_CLASS_MAP.get(dc) if dc else None

        # State class
        sc = sensor_def.get("state_class")
        self._attr_state_class = STATE_CLASS_MAP.get(sc) if sc else None

        # Unit
        unit = sensor_def.get("unit")
        if unit:
            self._attr_native_unit_of_measurement = unit

    @property
    def home_id(self) -> str:
        """Return home ID."""
        return self._home_id

    @property
    def sensor_key(self) -> str:
        """Return sensor key."""
        return self._sensor_key

    def set_currency(self, currency: str) -> None:
        """Set the currency unit for monetary sensors."""
        self._attr_native_unit_of_measurement = currency

    @callback
    def update_value(self, value: Any) -> None:
        """Update the sensor value and write state."""
        self._attr_native_value = value
        self.async_write_ha_state()


class TibberPriceSensor(SensorEntity):
    """Sensor for current electricity price."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        home_id: str,
        sensor_key: str,
        sensor_def: dict[str, Any],
        device_info: DeviceInfo,
        entry_id: str,
        runtime: TibberLiveData,
    ) -> None:
        """Initialize the price sensor."""
        self._home_id = home_id
        self._sensor_key = sensor_key
        self._runtime = runtime
        self._attr_name = sensor_def["name"]
        self._attr_unique_id = f"{home_id}_{sensor_key}"
        self._attr_icon = sensor_def.get("icon")
        self._attr_device_info = device_info
        self._attr_native_value = None

        dc = sensor_def.get("device_class")
        self._attr_device_class = DEVICE_CLASS_MAP.get(dc) if dc else None

        sc = sensor_def.get("state_class")
        self._attr_state_class = STATE_CLASS_MAP.get(sc) if sc else None

        # Set initial value from prices already fetched
        self._update_from_prices()

    def _update_from_prices(self) -> None:
        """Read the current price data and update value."""
        price = self._runtime.prices.get(self._home_id)
        if not price:
            return

        currency = price.get("currency", "")

        if self._sensor_key == "current_price_total":
            self._attr_native_value = price.get("total")
            if currency:
                self._attr_native_unit_of_measurement = f"{currency}/kWh"
        elif self._sensor_key == "current_price_energy":
            self._attr_native_value = price.get("energy")
            if currency:
                self._attr_native_unit_of_measurement = f"{currency}/kWh"
        elif self._sensor_key == "current_price_tax":
            self._attr_native_value = price.get("tax")
            if currency:
                self._attr_native_unit_of_measurement = f"{currency}/kWh"
        elif self._sensor_key == "price_level":
            self._attr_native_value = price.get("level")

    async def async_added_to_hass(self) -> None:
        """Register dispatcher listener when added."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_price_update",
                self._handle_price_update,
            )
        )

    @callback
    def _handle_price_update(self) -> None:
        """Handle price update from dispatcher."""
        self._update_from_prices()
        self.async_write_ha_state()

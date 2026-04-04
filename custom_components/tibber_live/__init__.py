"""The Tibber Live integration.

Streams real-time energy data from Tibber Pulse/Watty devices
and exposes sensors for power, consumption, cost, production,
and current electricity price per home.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .api import TibberApiClient
from .const import DOMAIN, CONF_TOKEN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


@dataclass
class TibberLiveData:
    """Runtime data stored in the config entry."""

    client: TibberApiClient
    homes: list[dict[str, Any]]
    prices: dict[str, dict[str, Any]] = field(default_factory=dict)
    unsubscribes: list = field(default_factory=list)
    price_task: asyncio.Task | None = None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Set up Tibber Live from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    client = TibberApiClient(entry.data[CONF_TOKEN])

    # Discover homes with real-time support
    homes = await client.async_get_homes()
    if not homes:
        _LOGGER.error("No Tibber homes with real-time support found")
        return False

    # Fetch initial prices
    prices = await client.async_get_prices()

    runtime = TibberLiveData(
        client=client,
        homes=homes,
        prices=prices,
    )
    hass.data[DOMAIN][entry.entry_id] = runtime

    # Forward to sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Start periodic price updater
    runtime.price_task = asyncio.create_task(
        _price_update_loop(hass, entry, runtime)
    )

    return True


async def _price_update_loop(
    hass: HomeAssistant,
    entry: ConfigEntry,
    runtime: TibberLiveData,
) -> None:
    """Refresh electricity prices every 60 seconds."""
    while True:
        await asyncio.sleep(60)
        try:
            new_prices = await runtime.client.async_get_prices()
            runtime.prices.update(new_prices)
            # Notify sensors via dispatcher
            from homeassistant.helpers.dispatcher import async_dispatcher_send
            async_dispatcher_send(hass, f"{DOMAIN}_price_update")
        except asyncio.CancelledError:
            return
        except Exception:
            _LOGGER.exception("Failed to update Tibber prices")


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Unload a Tibber Live config entry."""
    runtime: TibberLiveData = hass.data[DOMAIN][entry.entry_id]

    # Cancel price updater
    if runtime.price_task:
        runtime.price_task.cancel()
        try:
            await runtime.price_task
        except asyncio.CancelledError:
            pass

    # Unsubscribe WebSocket connections
    for unsub in runtime.unsubscribes:
        unsub()

    # Close API client
    await runtime.client.async_close()

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

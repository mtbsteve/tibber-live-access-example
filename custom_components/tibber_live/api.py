"""API client for Tibber Live integration."""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, Callable, Coroutine

import requests
import websockets

from .const import (
    TIBBER_API_URL,
    TIBBER_WS_URL,
    HOMES_QUERY,
    PRICE_QUERY,
    LIVE_SUBSCRIPTION,
)

_LOGGER = logging.getLogger(__name__)


class TibberApiClient:
    """Client for the Tibber GraphQL API."""

    def __init__(self, token: str) -> None:
        """Initialize the API client."""
        self._token = token
        self._subscriptions: dict[str, asyncio.Task] = {}

    @property
    def _headers(self) -> dict[str, str]:
        """Return HTTP headers with Bearer token."""
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    async def async_get_user(self) -> dict[str, Any] | None:
        """Validate token and return viewer name + homes."""
        return await asyncio.to_thread(self._get_user)

    def _get_user(self) -> dict[str, Any] | None:
        """Fetch viewer info (blocking)."""
        resp = requests.post(
            TIBBER_API_URL,
            json={"query": HOMES_QUERY},
            headers=self._headers,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            _LOGGER.error("Tibber API error: %s", data["errors"])
            return None
        return data["data"]["viewer"]

    async def async_get_homes(self) -> list[dict[str, Any]]:
        """Return list of homes with real-time enabled."""
        viewer = await self.async_get_user()
        if not viewer:
            return []
        return [
            h for h in viewer.get("homes", [])
            if h.get("features", {}).get("realTimeConsumptionEnabled")
        ]

    async def async_get_prices(self) -> dict[str, dict[str, Any]]:
        """Fetch current electricity prices for all homes."""
        return await asyncio.to_thread(self._get_prices)

    def _get_prices(self) -> dict[str, dict[str, Any]]:
        """Fetch current prices (blocking)."""
        try:
            resp = requests.post(
                TIBBER_API_URL,
                json={"query": PRICE_QUERY},
                headers=self._headers,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            if "errors" in data:
                _LOGGER.error("Tibber price query error: %s", data["errors"])
                return {}

            prices = {}
            for home in data["data"]["viewer"]["homes"]:
                sub = home.get("currentSubscription")
                if sub and sub.get("priceInfo") and sub["priceInfo"].get("current"):
                    price_info = dict(sub["priceInfo"]["current"])

                    # Compute min/max from today's prices
                    today = sub["priceInfo"].get("today", [])
                    if today:
                        totals = [p["total"] for p in today if p.get("total") is not None]
                        if totals:
                            price_info["minPriceToday"] = min(totals)
                            price_info["avgPriceToday"] = sum(totals) / len(totals)
                            price_info["maxPriceToday"] = max(totals)

                    prices[home["id"]] = price_info
            return prices
        except Exception:
            _LOGGER.exception("Failed to fetch Tibber prices")
            return {}

    async def async_subscribe_live(
        self,
        home_id: str,
        callback: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    ) -> Callable[[], None]:
        """Subscribe to live measurements for a home.

        Returns an unsubscribe callable.
        """
        task = asyncio.create_task(
            self._ws_subscription_loop(home_id, callback)
        )
        self._subscriptions[home_id] = task

        def unsubscribe() -> None:
            task.cancel()
            self._subscriptions.pop(home_id, None)

        return unsubscribe

    async def _ws_subscription_loop(
        self,
        home_id: str,
        callback: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    ) -> None:
        """Maintain a WebSocket subscription with automatic reconnect."""
        headers = {"Authorization": f"Bearer {self._token}"}

        while True:
            try:
                async with websockets.connect(
                    TIBBER_WS_URL,
                    subprotocols=["graphql-transport-ws"],
                    additional_headers=headers,
                ) as ws:
                    # connection_init
                    await ws.send(json.dumps({
                        "type": "connection_init",
                        "payload": {"token": self._token},
                    }))
                    ack = json.loads(await ws.recv())
                    if ack.get("type") != "connection_ack":
                        _LOGGER.error(
                            "Tibber WS not acknowledged for %s: %s",
                            home_id, ack,
                        )
                        await asyncio.sleep(30)
                        continue

                    _LOGGER.debug("Tibber WS connected for home %s", home_id)

                    # subscribe
                    sub_id = str(uuid.uuid4())
                    await ws.send(json.dumps({
                        "id": sub_id,
                        "type": "subscribe",
                        "payload": {
                            "query": LIVE_SUBSCRIPTION,
                            "variables": {"homeId": home_id},
                        },
                    }))

                    async for raw in ws:
                        msg = json.loads(raw)
                        msg_type = msg.get("type")

                        if msg_type == "next":
                            measurement = msg["payload"]["data"]["liveMeasurement"]
                            await callback(measurement)

                        elif msg_type == "error":
                            _LOGGER.error(
                                "Tibber subscription error for %s: %s",
                                home_id, msg.get("payload"),
                            )
                            break

                        elif msg_type == "complete":
                            _LOGGER.info(
                                "Tibber subscription completed for %s", home_id,
                            )
                            break

            except asyncio.CancelledError:
                _LOGGER.debug("Tibber WS subscription cancelled for %s", home_id)
                return

            except websockets.ConnectionClosed as exc:
                _LOGGER.warning(
                    "Tibber WS closed for %s: %s – reconnecting in 10 s",
                    home_id, exc,
                )

            except Exception:
                _LOGGER.exception(
                    "Tibber WS error for %s – reconnecting in 30 s", home_id,
                )
                await asyncio.sleep(20)  # extra wait on unexpected errors

            await asyncio.sleep(10)

    async def async_close(self) -> None:
        """Cancel all subscriptions."""
        for task in self._subscriptions.values():
            task.cancel()
        for task in self._subscriptions.values():
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._subscriptions.clear()

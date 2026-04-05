"""
Tibber Live API - Real-time energy measurement viewer (dual home, side-by-side).

Connects to the Tibber GraphQL API via WebSocket (graphql-transport-ws protocol)
and streams live measurement data from Tibber Pulse/Watty devices for all
real-time-enabled homes, displayed side by side in the terminal.

Authentication: OAuth2 Bearer token (https://developer.tibber.com/)
API docs: https://developer.tibber.com/docs/guides/calling-api
"""

import asyncio
import json
import os
import shutil
import sys
import uuid
from datetime import datetime

import requests
import websockets

# ── Configuration ────────────────────────────────────────────────────────────
TIBBER_API_URL = "https://api.tibber.com/v1-beta/gql"
TIBBER_WS_URL = "wss://websocket-api.tibber.com/v1-beta/gql/subscriptions"

# Set your token via environment variable or replace the fallback string
TIBBER_TOKEN = os.environ.get("TIBBER_TOKEN", "")

# ── GraphQL queries ──────────────────────────────────────────────────────────
HOMES_QUERY = """
{
  viewer {
    homes {
      id
      address {
        address1
        postalCode
        city
      }
      features {
        realTimeConsumptionEnabled
      }
    }
  }
}
"""

PRICE_QUERY = """
{
  viewer {
    homes {
      id
      currentSubscription {
        priceInfo(resolution: QUARTER_HOURLY) {
          current {
            total
            energy
            tax
            currency
            level
            startsAt
          }
          today {
            total
            startsAt
          }
        }
      }
    }
  }
}
"""

LIVE_SUBSCRIPTION = """
subscription($homeId: ID!) {
  liveMeasurement(homeId: $homeId) {
    timestamp
    power
    accumulatedConsumption
    accumulatedCost
    currency
    minPower
    averagePower
    maxPower
    powerProduction
    accumulatedProduction
    lastMeterProduction
    lastMeterConsumption
  }
}
"""

# Column width for side-by-side display
COL_WIDTH = 49


def get_headers() -> dict:
    """Return HTTP headers with OAuth2 Bearer token."""
    return {
        "Authorization": f"Bearer {TIBBER_TOKEN}",
        "Content-Type": "application/json",
    }


def fetch_rt_homes() -> list[dict]:
    """Fetch all homes with real-time consumption enabled."""
    print("Fetching your Tibber homes …")
    resp = requests.post(
        TIBBER_API_URL,
        json={"query": HOMES_QUERY},
        headers=get_headers(),
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    if "errors" in data:
        sys.exit(f"API error: {data['errors']}")

    homes = data["data"]["viewer"]["homes"]
    if not homes:
        sys.exit("No homes found on this Tibber account.")

    print(f"\nFound {len(homes)} home(s):\n")
    rt_homes = []
    for i, home in enumerate(homes, 1):
        addr = home["address"]
        rt = home["features"]["realTimeConsumptionEnabled"]
        print(f"  {i}. {addr['address1']}, {addr['postalCode']} {addr['city']}")
        print(f"     Home ID : {home['id']}")
        print(f"     Real-time: {'YES' if rt else 'NO'}")
        print()
        if rt:
            rt_homes.append(home)

    if not rt_homes:
        sys.exit(
            "No home with real-time consumption enabled. "
            "A Tibber Pulse or Watty device is required."
        )

    return rt_homes


def fetch_current_prices() -> dict[str, dict]:
    """Fetch the current electricity price for all homes. Returns {home_id: price_info}."""
    resp = requests.post(
        TIBBER_API_URL,
        json={"query": PRICE_QUERY},
        headers=get_headers(),
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    if "errors" in data:
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
                    price_info["maxPriceToday"] = max(totals)
                    price_info["avgPriceToday"] = sum(totals) / len(totals)

            prices[home["id"]] = price_info
    return prices


def format_value(label: str, value, unit: str = "", fmt: str = ".1f") -> str:
    """Format a single metric as 'Label : value unit'."""
    if value is None:
        return f"{label}: {'n/a':>{10}}"
    return f"{label}: {value:>{10}{fmt}} {unit}"


def build_column(m: dict, price: dict | None = None) -> list[str]:
    """Build display lines for one home's measurement."""
    ts = m.get("timestamp", "")
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        ts_display = dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, AttributeError):
        ts_display = ts

    currency = m.get("currency", "")

    lines = [
        f"  Time             : {ts_display}",
    ]

    # Current electricity price
    if price:
        p_currency = price.get("currency", currency)
        level = price.get("level", "")
        lines.append(f"  {format_value('Price (15 min)   ', price.get('total'), f'{p_currency}/kWh', '.4f')}")
        lines.append(f"  {format_value('  Energy         ', price.get('energy'), f'{p_currency}/kWh', '.4f')}")
        lines.append(f"  {format_value('  Tax            ', price.get('tax'), f'{p_currency}/kWh', '.4f')}")
        lines.append(f"  Price Level      : {level:>{10}}")
        lines.append(f"  {format_value('Min Price Today  ', price.get('minPriceToday'), f'{p_currency}/kWh', '.4f')}")
        lines.append(f"  {format_value('Avg Price Today  ', price.get('avgPriceToday'), f'{p_currency}/kWh', '.4f')}")
        lines.append(f"  {format_value('Max Price Today  ', price.get('maxPriceToday'), f'{p_currency}/kWh', '.4f')}")
    else:
        lines.append(f"  Price (15 min)   : {'n/a':>{10}}")
        lines.append(f"  {'':>17}  {'':>{10}}")
        lines.append(f"  {'':>17}  {'':>{10}}")
        lines.append(f"  {'':>17}  {'':>{10}}")
        lines.append(f"  {'':>17}  {'':>{10}}")
        lines.append(f"  {'':>17}  {'':>{10}}")
        lines.append(f"  {'':>17}  {'':>{10}}")

    lines.extend([
        f"  {format_value('Power            ', m.get('power'), 'W')}",
        f"  {format_value('Accum Consumption', m.get('accumulatedConsumption'), 'kWh', '.3f')}",
        f"  {format_value('Accum Cost       ', m.get('accumulatedCost'), currency, '.2f')}",
        f"  {format_value('Min Power        ', m.get('minPower'), 'W')}",
        f"  {format_value('Avg Power        ', m.get('averagePower'), 'W')}",
        f"  {format_value('Max Power        ', m.get('maxPower'), 'W')}",
        f"  {format_value('Power Production ', m.get('powerProduction'), 'W')}",
        f"  {format_value('Accum Production ', m.get('accumulatedProduction'), 'kWh', '.3f')}",
        f"  {format_value('Last Meter Prod. ', max(m.get('lastMeterProduction') or 0, 0), 'kWh', '.3f')}",
        f"  {format_value('Last Meter Cons. ', m.get('lastMeterConsumption'), 'kWh', '.3f')}",
    ])

    return lines


def render_side_by_side(
    home_ids: list[str],
    id_to_label: dict[str, str],
    data: dict[str, dict],
    prices: dict[str, dict],
) -> str:
    """Render the latest measurements for all homes side by side."""
    term_width = shutil.get_terminal_size((100, 24)).columns
    col_w = max(COL_WIDTH, term_width // len(home_ids) - 3)
    separator = " │ "

    # Header uses friendly labels
    header = separator.join(id_to_label[hid].center(col_w) for hid in home_ids)
    divider = separator.join("─" * col_w for _ in home_ids)

    # Data keyed by home_id
    columns: list[list[str]] = []
    for hid in home_ids:
        m = data.get(hid)
        if m:
            columns.append(build_column(m, prices.get(hid)))
        else:
            columns.append(["  (waiting for data …)"] + [""] * 16)

    # Zip rows together
    rows = []
    for parts in zip(*columns):
        row = separator.join(part.ljust(col_w) for part in parts)
        rows.append(row)

    return "\n".join(["", header, divider] + rows + [divider])


async def subscribe_home(
    home_id: str,
    label: str,
    latest: dict,
    update_event: asyncio.Event,
) -> None:
    """Subscribe to live data for a single home and update shared state."""
    headers = {"Authorization": f"Bearer {TIBBER_TOKEN}"}

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
                    "payload": {"token": TIBBER_TOKEN},
                }))
                ack = json.loads(await ws.recv())
                if ack.get("type") != "connection_ack":
                    print(f"[{label}] Connection not acknowledged: {ack}")
                    return

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
                        latest[label] = msg["payload"]["data"]["liveMeasurement"]
                        update_event.set()

                    elif msg_type == "error":
                        print(f"[{label}] Subscription error: {msg.get('payload')}")
                        break

                    elif msg_type == "complete":
                        print(f"[{label}] Subscription completed by server.")
                        break

        except websockets.ConnectionClosed as exc:
            print(f"\n[{label}] WebSocket closed: {exc}  – reconnecting in 5 s …")
            await asyncio.sleep(5)
        except Exception as exc:
            print(f"\n[{label}] Error: {exc}  – reconnecting in 5 s …")
            await asyncio.sleep(5)


async def price_updater(
    prices: dict[str, dict],
    update_event: asyncio.Event,
) -> None:
    """Periodically refresh the current electricity price (every 60 seconds).

    Tibber uses quarter-hourly (15-min) pricing since Oct 2025 (EPEX Spot).
    We poll every 60 s so the display updates promptly at each 15-min boundary.
    """
    while True:
        try:
            new_prices = await asyncio.to_thread(fetch_current_prices)
            prices.update(new_prices)
            update_event.set()
        except Exception as exc:
            print(f"[price] Failed to fetch prices: {exc}")
        await asyncio.sleep(60)  # poll every 60 s to catch 15-min price changes


async def display_loop(
    home_ids: list[str],
    id_to_label: dict[str, str],
    latest: dict,
    prices: dict[str, dict],
    update_event: asyncio.Event,
) -> None:
    """Re-render the side-by-side view whenever new data arrives."""
    while True:
        await update_event.wait()
        update_event.clear()

        # Clear screen and redraw
        print("\033[2J\033[H", end="")  # ANSI clear screen + cursor home
        print("TIBBER LIVE  ─  Real-time energy data")
        print("Press Ctrl+C to stop.\n")
        print(render_side_by_side(home_ids, id_to_label, latest, prices))


async def run(rt_homes: list[dict]) -> None:
    """Launch subscriptions for all homes and the display loop."""
    latest: dict[str, dict] = {}
    prices: dict[str, dict] = {}
    update_event = asyncio.Event()

    # Map home_id -> display label (guaranteed unique keys)
    home_ids = []
    id_to_label: dict[str, str] = {}
    tasks = []
    for idx, home in enumerate(rt_homes, 1):
        addr = home["address"]
        home_id = home["id"]
        label = f"Home {idx}: {addr['address1']}, {addr['city']}"
        home_ids.append(home_id)
        id_to_label[home_id] = label
        tasks.append(
            asyncio.create_task(
                subscribe_home(home_id, home_id, latest, update_event)
            )
        )

    # Price updater task (refreshes every 5 minutes)
    tasks.append(asyncio.create_task(
        price_updater(prices, update_event)
    ))

    # Display task uses home_ids as keys but id_to_label for headers
    tasks.append(asyncio.create_task(
        display_loop(home_ids, id_to_label, latest, prices, update_event)
    ))

    print("Connecting to Tibber WebSocket for all homes …\n")
    await asyncio.gather(*tasks)


def main() -> None:
    if not TIBBER_TOKEN:
        sys.exit(
            "No API token found.\n"
            "Set the TIBBER_TOKEN environment variable or edit TIBBER_TOKEN in this script.\n"
            "Get your token at https://developer.tibber.com/"
        )

    rt_homes = fetch_rt_homes()
    print(f"Subscribing to {len(rt_homes)} home(s) …\n")
    print("Press Ctrl+C to stop.\n")

    try:
        asyncio.run(run(rt_homes))
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()

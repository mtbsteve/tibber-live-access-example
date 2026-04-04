# Tibber Live Access Example

Real-time energy measurement viewer that connects to the [Tibber API](https://developer.tibber.com/) and streams live data from your Tibber Pulse or Watty device directly to your terminal.

If you have multiple homes with real-time support, the data is displayed **side by side**.

## Features

- **OAuth2 Bearer token** authentication
- Auto-discovery of all homes on your Tibber account
- Dual-home side-by-side live display
- **Quarter-hourly (15-min) electricity price** display (total, energy, tax, price level) — uses EPEX Spot 15-min resolution, refreshed every 60 seconds
- Real-time fields: power, accumulated consumption, accumulated cost, currency, min/avg/max power, power production, accumulated production
- Auto-reconnect on connection loss

## Prerequisites

- **Python 3.10+**
- A **Tibber account** with a [Tibber Pulse](https://tibber.com/de/pulse) or Watty device connected to your smart meter
- A **Tibber API token** (personal access token)

## Getting Your API Token

1. Go to [https://developer.tibber.com/](https://developer.tibber.com/)
2. Sign in with your Tibber account
3. Open the **API Explorer**
4. Click **"Load personal token"** to reveal your token
5. Copy the token for use below

## Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/mtbsteve/tibber-live-access-example.git
   cd tibber-live-access-example
   ```

2. **Create a virtual environment** (recommended)

   ```bash
   python -m venv venv

   # Linux / macOS
   source venv/bin/activate

   # Windows (CMD)
   venv\Scripts\activate.bat

   # Windows (PowerShell)
   venv\Scripts\Activate.ps1
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. **Set your Tibber API token** as an environment variable:

   ```bash
   # Linux / macOS
   export TIBBER_TOKEN="your-token-here"

   # Windows (CMD)
   set TIBBER_TOKEN=your-token-here

   # Windows (PowerShell)
   $env:TIBBER_TOKEN="your-token-here"
   ```

2. **Run the program**

   ```bash
   python tibber_live.py
   ```

3. The program will:
   - Fetch all homes linked to your Tibber account
   - Display each home's ID and real-time capability
   - Fetch the current 15-minute electricity price for each home
   - Subscribe to live measurements via WebSocket
   - Stream data to your terminal in real time (prices refresh every 60 seconds)

4. **Press `Ctrl+C`** to stop.

## Example Output

```
TIBBER LIVE  -  Real-time energy data
Press Ctrl+C to stop.

     Home 1: Musterstr. 1, Berlin          |       Home 2: Beispielweg 5, Muenchen
--------------------------------------------|-----------------------------------------
  Time             : 2026-04-04 14:23:01    |   Time             : 2026-04-04 14:23:02
  Price (15 min)   :     0.2835 EUR/kWh     |   Price (15 min)   :     0.3012 EUR/kWh
    Energy         :     0.1200 EUR/kWh     |     Energy         :     0.1350 EUR/kWh
    Tax            :     0.1635 EUR/kWh     |     Tax            :     0.1662 EUR/kWh
  Price Level      :     NORMAL             |   Price Level      :     EXPENSIVE
  Power            :     1234.0 W           |   Power            :      567.0 W
  Accum Consumption:       12.345 kWh       |   Accum Consumption:        5.678 kWh
  Accum Cost       :        3.45 EUR        |   Accum Cost       :        1.23 EUR
  Min Power        :      100.0 W           |   Min Power        :       50.0 W
  Avg Power        :      800.0 W           |   Avg Power        :      400.0 W
  Max Power        :     2000.0 W           |   Max Power        :     1000.0 W
  Power Production :        0.0 W           |   Power Production :      250.0 W
  Accum Production :        0.000 kWh       |   Accum Production :        1.234 kWh
--------------------------------------------|-----------------------------------------
```

## API Reference

- **GraphQL endpoint:** `https://api.tibber.com/v1-beta/gql`
- **WebSocket endpoint:** `wss://websocket-api.tibber.com/v1-beta/gql/subscriptions`
- **Protocol:** `graphql-transport-ws`
- **Tibber API docs:** [https://developer.tibber.com/docs/guides/calling-api](https://developer.tibber.com/docs/guides/calling-api)

## License

MIT

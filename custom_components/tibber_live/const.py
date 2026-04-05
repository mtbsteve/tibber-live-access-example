"""Constants for the Tibber Live integration."""

DOMAIN = "tibber_live"

TIBBER_API_URL = "https://api.tibber.com/v1-beta/gql"
TIBBER_WS_URL = "wss://websocket-api.tibber.com/v1-beta/gql/subscriptions"

CONF_TOKEN = "token"

# GraphQL queries
HOMES_QUERY = """
{
  viewer {
    name
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

# Sensor definitions: (key, name, device_class, state_class, unit, icon)
LIVE_SENSOR_TYPES = {
    "power": {
        "name": "Power",
        "device_class": "power",
        "state_class": "measurement",
        "unit": "W",
        "icon": "mdi:flash",
    },
    "min_power": {
        "name": "Min Power",
        "device_class": "power",
        "state_class": "measurement",
        "unit": "W",
        "icon": "mdi:flash-outline",
    },
    "average_power": {
        "name": "Average Power",
        "device_class": "power",
        "state_class": "measurement",
        "unit": "W",
        "icon": "mdi:flash",
    },
    "max_power": {
        "name": "Max Power",
        "device_class": "power",
        "state_class": "measurement",
        "unit": "W",
        "icon": "mdi:flash-alert",
    },
    "accumulated_consumption": {
        "name": "Accumulated Consumption",
        "device_class": "energy",
        "state_class": "total_increasing",
        "unit": "kWh",
        "icon": "mdi:lightning-bolt",
    },
    "accumulated_cost": {
        "name": "Accumulated Cost",
        "device_class": "monetary",
        "state_class": "total_increasing",
        "unit": None,  # set dynamically from currency
        "icon": "mdi:currency-eur",
    },
    "power_production": {
        "name": "Power Production",
        "device_class": "power",
        "state_class": "measurement",
        "unit": "W",
        "icon": "mdi:solar-power",
    },
    "accumulated_production": {
        "name": "Accum Production",
        "device_class": "energy",
        "state_class": "total_increasing",
        "unit": "kWh",
        "icon": "mdi:solar-power",
    },
    "last_meter_production": {
        "name": "Last Meter Production",
        "device_class": "energy",
        "state_class": "total_increasing",
        "unit": "kWh",
        "icon": "mdi:solar-power-variant",
    },
    "last_meter_consumption": {
        "name": "Last Meter Consumption",
        "device_class": "energy",
        "state_class": "total_increasing",
        "unit": "kWh",
        "icon": "mdi:meter-electric",
    },
}

PRICE_SENSOR_TYPES = {
    "current_price_total": {
        "name": "Electricity Price (15 min)",
        "device_class": "monetary",
        "state_class": "measurement",
        "unit": None,  # set dynamically
        "icon": "mdi:currency-eur",
    },
    "current_price_energy": {
        "name": "Electricity Price Energy",
        "device_class": "monetary",
        "state_class": "measurement",
        "unit": None,
        "icon": "mdi:lightning-bolt-circle",
    },
    "current_price_tax": {
        "name": "Electricity Price Tax",
        "device_class": "monetary",
        "state_class": "measurement",
        "unit": None,
        "icon": "mdi:receipt-text",
    },
    "price_level": {
        "name": "Price Level",
        "device_class": None,
        "state_class": None,
        "unit": None,
        "icon": "mdi:tag",
    },
    "price_min_today": {
        "name": "Min Price Today",
        "device_class": "monetary",
        "state_class": "measurement",
        "unit": None,
        "icon": "mdi:arrow-down-bold",
    },
    "price_avg_today": {
        "name": "Avg Price Today",
        "device_class": "monetary",
        "state_class": "measurement",
        "unit": None,
        "icon": "mdi:chart-line-variant",
    },
    "price_max_today": {
        "name": "Max Price Today",
        "device_class": "monetary",
        "state_class": "measurement",
        "unit": None,
        "icon": "mdi:arrow-up-bold",
    },
}

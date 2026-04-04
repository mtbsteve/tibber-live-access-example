"""Config flow for Tibber Live integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .api import TibberApiClient
from .const import DOMAIN, CONF_TOKEN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TOKEN): str,
    }
)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidToken(HomeAssistantError):
    """Error to indicate invalid authentication token."""


class NoRealTimeHomes(HomeAssistantError):
    """Error to indicate no homes with real-time support."""


async def validate_input(
    hass: HomeAssistant,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Validate the user input by testing the API connection."""
    client = TibberApiClient(data[CONF_TOKEN])

    try:
        viewer = await client.async_get_user()
    except Exception as err:
        raise CannotConnect from err

    if not viewer:
        raise InvalidToken

    homes = [
        h for h in viewer.get("homes", [])
        if h.get("features", {}).get("realTimeConsumptionEnabled")
    ]

    if not homes:
        raise NoRealTimeHomes

    viewer_name = viewer.get("name", "Tibber")
    home_count = len(homes)
    title = f"{viewer_name} ({home_count} home{'s' if home_count > 1 else ''})"

    return {"title": title}


class TibberLiveConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tibber Live."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step — API token input."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
            )

        errors: dict[str, str] = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidToken:
            errors["base"] = "invalid_token"
        except NoRealTimeHomes:
            errors["base"] = "no_realtime_homes"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected error during config flow")
            errors["base"] = "unknown"
        else:
            # Prevent duplicate entries for the same token
            await self.async_set_unique_id(user_input[CONF_TOKEN][:16])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=info["title"],
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

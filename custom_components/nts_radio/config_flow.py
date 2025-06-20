"""Config flow for NTS Radio integration."""

import logging
from typing import Any, Dict

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    CONF_IGNORE_UNKNOWN_TRACKS,
    DEFAULT_IGNORE_UNKNOWN_TRACKS,
    MIN_UPDATE_INTERVAL,
    MAX_UPDATE_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=MIN_UPDATE_INTERVAL, max=MAX_UPDATE_INTERVAL)
        ),
        vol.Optional(CONF_EMAIL): str,
        vol.Optional(CONF_PASSWORD): str,
        vol.Optional(CONF_IGNORE_UNKNOWN_TRACKS, default=DEFAULT_IGNORE_UNKNOWN_TRACKS): bool,
    }
)

# Reusable schema builder for options
def _build_options_schema(entry: config_entries.ConfigEntry) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(
                CONF_UPDATE_INTERVAL,
                default=entry.options.get(
                    CONF_UPDATE_INTERVAL,
                    entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=MIN_UPDATE_INTERVAL, max=MAX_UPDATE_INTERVAL)),
            vol.Optional(
                CONF_IGNORE_UNKNOWN_TRACKS,
                default=entry.options.get(
                    CONF_IGNORE_UNKNOWN_TRACKS,
                    entry.data.get(CONF_IGNORE_UNKNOWN_TRACKS, DEFAULT_IGNORE_UNKNOWN_TRACKS),
                ),
            ): bool,
        }
    )

async def validate_input(hass: HomeAssistant, data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the user input allows us to connect."""
    # No validation needed for NTS Radio public API
    # Authentication validation will happen when trying to connect to Firebase
    return {"title": "NTS Radio"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NTS Radio."""

    VERSION = 1

    # ---------- options flow ----------

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):  # type: ignore[override]
        """Return the options flow handler."""
        return NTSOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: Dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        # Enforce single instance of the integration.
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            # Check if already configured
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()

            # Remove empty authentication fields
            if user_input.get(CONF_EMAIL) == "":
                user_input.pop(CONF_EMAIL, None)
            if user_input.get(CONF_PASSWORD) == "":
                user_input.pop(CONF_PASSWORD, None)

            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class NTSOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle integration options."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self.config_entry = entry

    async def async_step_init(self, user_input: Dict[str, Any] | None = None):  # type: ignore[override]
        if user_input is None:
            return self.async_show_form(
                step_id="init",
                data_schema=_build_options_schema(self.config_entry),
            )

        # Clean up input (remove empty values)
        data = user_input.copy()

        return self.async_create_entry(title="", data=data)

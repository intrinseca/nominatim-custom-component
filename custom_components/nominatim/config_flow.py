"""Adds config flow for Nominatim."""
import voluptuous as vol
from homeassistant import config_entries

from .const import (
    CONF_OSM_USERNAME,
    CONF_SOURCE,
    DOMAIN,
)


class NominatimFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore
    """Config flow for nominatim."""

    VERSION = 3
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize."""
        self._errors = {}

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            return self.async_create_entry(
                title=f"{user_input[CONF_SOURCE]} Nominatim", data=user_input
            )

        return await self._show_config_form(user_input)

    async def _show_config_form(self, user_input):  # pylint: disable=unused-argument
        """Show the configuration form to edit location data."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SOURCE): str,
                    vol.Required(CONF_OSM_USERNAME): str,
                }
            ),
            errors=self._errors,
        )

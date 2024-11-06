"""Custom integration to integrate Nominatim with Home Assistant.

For more details about this integration, please refer to
https://github.com/intrinseca/nominatim-custom-component
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta

from geopy.location import Location
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import NominatimApiClient
from .const import (
    CONF_OSM_USERNAME,
    CONF_SOURCE,
    DOMAIN,
    PLATFORMS,
)

SCAN_INTERVAL = timedelta(minutes=5)

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up this integration using UI."""
    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})

    username = entry.data.get(CONF_OSM_USERNAME)

    source = entry.data.get(CONF_SOURCE)
    client = NominatimApiClient(username)

    coordinator = NominatimDataUpdateCoordinator(hass, client=client, source=source)

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.add_update_listener(async_reload_entry)
    return True


@dataclass
class NominatimData:
    """Hold the data pulled from the APIs."""

    origin_reverse_geocode: Location

    @property
    def origin_address(self) -> str:
        """Get the suitable address string from the reverse geocoding lookup."""
        if self.origin_reverse_geocode is not None:
            for key in ["village", "suburb", "town", "city", "state", "country"]:
                if key in self.origin_reverse_geocode.raw["address"]:
                    return self.origin_reverse_geocode.raw["address"][key]

        return "Unknown"


def get_location_from_attributes(entity):
    """Get the lat/long string from an entities attributes."""
    attr = entity.attributes
    try:
        return (float(attr.get(ATTR_LATITUDE)), float(attr.get(ATTR_LONGITUDE)))
    except ValueError:
        return None


# type: ignore
class NominatimDataUpdateCoordinator(DataUpdateCoordinator[NominatimData]):
    """Class to manage fetching data from the API."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: NominatimApiClient,
        source: str,
    ) -> None:
        """Initialize."""

        self.api = client

        self._source_entity_id = source

        async_track_state_change_event(
            hass, self._source_entity_id, self._handle_origin_state_change
        )

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            update_method=self.update,
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=1800, immediate=True
            ),
        )

    async def _handle_origin_state_change(self, event: Event):
        if event.data["old_state"].state == event.data["new_state"].state:
            if self.data is None:
                _LOGGER.debug(
                    "Origin %s updated, no previous data, forcing refresh",
                    self._source_entity_id,
                )
                await self.async_refresh()
            else:
                _LOGGER.debug(
                    "Origin %s updated without state change, requesting refresh",
                    self._source_entity_id,
                )
                await self.async_request_refresh()
        else:
            _LOGGER.debug(
                "Origin %s updated *with* state change, forcing refresh",
                self._source_entity_id,
            )
            await self.async_refresh()

    async def update(self):
        """Update data via library."""
        try:
            source_entity = self.hass.states.get(self._source_entity_id)
            source = get_location_from_attributes(source_entity)

            if source is not None:
                address = await self.api.async_get_address(source)
            else:
                _LOGGER.error(
                    "Unable to get source coordinates from %s", self._source_entity_id
                )
                address = None

            return NominatimData(address)
        except Exception as exception:
            raise UpdateFailed(str(exception)) from exception


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    unloaded = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)

"""
Custom integration to integrate Journey with Home Assistant.

For more details about this integration, please refer to
https://github.com/intrinseca/journey
"""
import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LATITUDE
from homeassistant.const import ATTR_LONGITUDE
from homeassistant.core import Config
from homeassistant.core import Event
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import location
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed

from .api import JourneyApiClient
from .const import CONF_DESTINATION
from .const import CONF_GMAPS_TOKEN
from .const import CONF_ORIGIN
from .const import CONF_OSM_USERNAME
from .const import DOMAIN
from .const import PLATFORMS
from .const import STARTUP_MESSAGE

SCAN_INTERVAL = timedelta(minutes=5)

_LOGGER: logging.Logger = logging.getLogger(__package__)


# pylint: disable=unused-argument
async def async_setup(hass: HomeAssistant, config: Config):
    """Set up this integration using YAML is not supported."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up this integration using UI."""
    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})
        _LOGGER.info(STARTUP_MESSAGE)

    username = entry.data.get(CONF_OSM_USERNAME)
    password = entry.data.get(CONF_GMAPS_TOKEN)

    origin = entry.data.get(CONF_ORIGIN)
    destination = entry.data.get(CONF_DESTINATION)
    client = JourneyApiClient(username, password)

    coordinator = JourneyDataUpdateCoordinator(
        hass, client=client, origin=origin, destination=destination
    )
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data[DOMAIN][entry.entry_id] = coordinator

    for platform in PLATFORMS:
        if entry.options.get(platform, True):
            coordinator.platforms.append(platform)
            hass.async_add_job(
                hass.config_entries.async_forward_entry_setup(entry, platform)
            )

    entry.add_update_listener(async_reload_entry)
    return True


def get_location_from_entity(hass, logger, entity_id):
    """Get the location from the entity state or attributes."""
    if (entity := hass.states.get(entity_id)) is None:
        logger.error("Unable to find entity %s", entity_id)
        return None

    # Check if the entity has location attributes
    if location.has_location(entity):
        logger.debug("%s has coords", entity_id)
        return get_location_from_attributes(entity)

    # Check if device is in a zone
    if (zone_entity := hass.states.get(f"zone.{entity.state}")) is None:
        logger.error("zone %s not found", entity.state)
        return None

    if location.has_location(zone_entity):
        logger.debug(
            "%s is in %s, getting zone location", entity_id, zone_entity.entity_id
        )
        return get_location_from_attributes(zone_entity)
    else:
        logger.debug("%s is in %s, no zone location", entity_id, zone_entity.entity_id)

    # When everything fails just return nothing
    return None


def get_location_from_attributes(entity):
    """Get the lat/long string from an entities attributes."""
    attr = entity.attributes
    return (float(attr.get(ATTR_LATITUDE)), float(attr.get(ATTR_LONGITUDE)))


class JourneyDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: JourneyApiClient,
        origin: str,
        destination: str,
    ) -> None:
        """Initialize."""
        self.api = client
        self.platforms = []

        self._origin_entity_id = origin
        self._destination_entity_id = destination

        async_track_state_change_event(
            hass, self._origin_entity_id, self._handle_state_change
        )

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            update_method=self.update,
        )

    async def _handle_state_change(self, event: Event):
        await self.async_request_refresh()

    async def update(self):
        """Update data via library."""
        try:
            origin = get_location_from_entity(
                self.hass, _LOGGER, self._origin_entity_id
            )
            destination = get_location_from_entity(
                self.hass, _LOGGER, self._destination_entity_id
            )
            return await self.api.async_get_data(origin, destination)
        except Exception as exception:
            raise UpdateFailed() from exception


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    unloaded = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
                if platform in coordinator.platforms
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

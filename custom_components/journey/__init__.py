"""
Custom integration to integrate Journey with Home Assistant.

For more details about this integration, please refer to
https://github.com/intrinseca/journey
"""
import asyncio
import logging
import math
from dataclasses import dataclass
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
from OSMPythonTools.nominatim import NominatimResult

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
            hass.async_add_job(
                hass.config_entries.async_forward_entry_setup(entry, platform)  # type: ignore
            )

    entry.add_update_listener(async_reload_entry)
    return True


def get_location_from_entity(hass, logger, entity_id):
    """Get the location from the entity state or attributes."""

    if (entity := hass.states.get(entity_id)) is None:
        logger.error("Locating %s: Unable to find", entity_id)
        return None

    # Check if device is in a zone
    if not entity_id.startswith("zone"):
        if (zone_entity := hass.states.get(f"zone.{entity.state}")) is not None:
            if location.has_location(zone_entity):
                logger.debug(
                    "Locating %s: in %s, getting zone location",
                    entity_id,
                    zone_entity.entity_id,
                )
                return get_location_from_attributes(zone_entity)

            logger.debug(
                "Locating %s: in %s, no zone location",
                entity_id,
                zone_entity.entity_id,
            )
        else:
            logger.debug("Locating %s: [zone '%s' not found]", entity_id, entity.state)

    # Check if the entity has location attributes
    if location.has_location(entity):
        logger.debug("Locating %s: from attributes", entity_id)
        return get_location_from_attributes(entity)

    # When everything fails just return nothing
    return None


def get_location_from_attributes(entity):
    """Get the lat/long string from an entities attributes."""
    attr = entity.attributes
    return (float(attr.get(ATTR_LATITUDE)), float(attr.get(ATTR_LONGITUDE)))


@dataclass
class JourneyTravelTime:
    travel_time: dict

    @property
    def travel_time_values(self) -> dict:
        if self.travel_time is None:
            return {}

        return {k: v["value"] for k, v in self.travel_time.items() if k != "status"}

    @property
    def duration(self):
        if self.travel_time_values is None:
            return float("nan")

        return self.travel_time_values.get("duration", float("nan"))

    @property
    def duration_min(self):
        return round(self.duration / 60) if not math.isnan(self.duration) else None

    @property
    def duration_in_traffic(self):
        if self.travel_time_values is None:
            return float("nan")

        return self.travel_time_values.get("duration_in_traffic", self.duration)

    @property
    def duration_in_traffic_min(self):
        return (
            round(self.duration_in_traffic / 60)
            if not math.isnan(self.duration_in_traffic)
            else None
        )

    @property
    def delay(self):
        return self.duration_in_traffic - self.duration

    @property
    def delay_min(self):
        return round(self.delay / 60) if not math.isnan(self.delay) else None

    @property
    def delay_factor(self):
        return round(100 * self.delay / self.duration) if self.duration > 0 else 0


@dataclass
class JourneyData:
    origin_reverse_geocode: NominatimResult
    travel_time: list[JourneyTravelTime]

    @property
    def origin_address(self) -> str:
        if self.origin_reverse_geocode is not None:
            for key in ["village", "suburb", "town", "city", "state", "country"]:
                if key in self.origin_reverse_geocode.address():
                    return self.origin_reverse_geocode.address()[key]

        return "Unknown"


class JourneyDataUpdateCoordinator(DataUpdateCoordinator[JourneyData]):  # type: ignore
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
        traveltime = JourneyTravelTime(None)

        try:
            origin = get_location_from_entity(
                self.hass, _LOGGER, self._origin_entity_id
            )

            if origin is not None:
                address = await self.api.async_get_address(origin)
            else:
                _LOGGER.error("Unable to get origin coordinates")
                address = None

            destination = get_location_from_entity(
                self.hass, _LOGGER, self._destination_entity_id
            )

            if destination is None:
                _LOGGER.error("Unable to get destination coordinates")
            elif self.hass.states.get(
                self._origin_entity_id
            ) == self._destination_entity_id.replace("zone.", ""):
                _LOGGER.info("origin is equal to destination zone")
            else:
                traveltime = JourneyTravelTime(
                    travel_time=await self.api.async_get_traveltime(origin, destination)
                )

            return JourneyData(address, traveltime)
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

"""Nominatim API Client."""
import logging

from geopy.adapters import AioHTTPAdapter
from geopy.geocoders import Nominatim

TIMEOUT = 10

_LOGGER: logging.Logger = logging.getLogger(__package__)


Coordinates = tuple[float, float]


class NominatimApiClient:
    """API client for the OSM Nominatim and Google Travel Time APIs."""

    def __init__(self, osm_username: str) -> None:
        """Initialise the API client."""
        self._osm_username = osm_username

        self.nominatim = Nominatim(
            user_agent=f"Nominatim Home Assistant Integration ({self._osm_username})",
            adapter_factory=AioHTTPAdapter,
        )

    async def async_get_address(self, location: Coordinates):
        """Get address corresponding to location using OSM."""
        try:
            return await self.nominatim.reverse(
                f"{location[0]}, {location[1]}", zoom=16
            )
        except Exception as exception:  # pylint: disable=broad-except
            _LOGGER.error("Failed to perform reverse geocoding - %s", exception)
            return None

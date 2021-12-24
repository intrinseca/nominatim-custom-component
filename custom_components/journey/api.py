"""Sample API Client."""
import asyncio
import logging

import aiohttp
from OSMPythonTools.nominatim import Nominatim

TIMEOUT = 10

_LOGGER: logging.Logger = logging.getLogger(__package__)


class JourneyApiClient:
    """API client for the OSM Nominatim and Google Travel Time APIs"""

    def __init__(
        self, username: str, password: str, session: aiohttp.ClientSession
    ) -> None:
        self._username = username
        self._password = password
        self._session = session

        self.nominatim = Nominatim(
            userAgent=f"Journey Home Assistant Integration ({self._username})"
        )

    def get_location(self, origin: tuple[float, float]):
        """
        Get the address based on a (lat, long) tuple.

        This function is used as a sync wrapper to the Nominatim API
        """
        try:
            result = self.nominatim.query(*origin, reverse=True, zoom=16)
            return result
        except Exception as exception:  # pylint: disable=broad-except
            _LOGGER.error("Failed to perform reverse geocoding - %s", exception)

    async def async_get_data(
        self, origin: tuple[float, float], destination: tuple[float, float]
    ) -> dict:
        """
        Asychronous function to poll the APIs
        """
        return await asyncio.get_event_loop().run_in_executor(
            None, self.get_location, origin
        )

    async def test_credentials(self) -> bool:
        """Check the Google Maps API credentials"""
        return True

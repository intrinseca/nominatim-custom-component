"""Sample API Client."""
import asyncio
import logging
import socket

import aiohttp
import async_timeout

from OSMPythonTools.nominatim import Nominatim

TIMEOUT = 10

_LOGGER: logging.Logger = logging.getLogger(__package__)


class JourneyApiClient:
    def __init__(
        self, username: str, password: str, session: aiohttp.ClientSession
    ) -> None:
        """Sample API Client."""
        self._username = username
        self._password = password
        self._session = session

        self.nominatim = Nominatim()

    def get_location(
        self, origin: tuple[float, float], destination: tuple[float, float]
    ):
        try:
            result = self.nominatim.query(*origin, reverse=True, zoom=14)
            return result
        except Exception as exception:  # pylint: disable=broad-except
            _LOGGER.error("Failed to perform reverse geocoding - %s", exception)

    async def async_get_data(
        self, origin: tuple[float, float], destination: tuple[float, float]
    ) -> dict:
        return await asyncio.get_event_loop().run_in_executor(
            None, self.get_location, origin, destination
        )

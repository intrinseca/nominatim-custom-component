"""Sample API Client."""
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime

from googlemaps import Client
from OSMPythonTools.nominatim import Nominatim

TIMEOUT = 10

_LOGGER: logging.Logger = logging.getLogger(__package__)


@dataclass
class JourneyData:
    origin_reverse_geocode: dict
    distance_matrix: dict

    def origin_address(self) -> str:
        if self.origin_reverse_geocode is not None:
            for key in ["village", "suburb", "town", "city", "state", "country"]:
                if key in self.origin_reverse_geocode.address():
                    return self.origin_reverse_geocode.address()[key]

        return "Unknown"


class JourneyApiClient:
    """API client for the OSM Nominatim and Google Travel Time APIs"""

    def __init__(self, osm_username: str, gmaps_token: str) -> None:
        self._osm_username = osm_username
        self._gmaps_token = gmaps_token

        self._gmaps_client = Client(gmaps_token, timeout=10)

        self.nominatim = Nominatim(
            userAgent=f"Journey Home Assistant Integration ({self._osm_username})"
        )

    def get_address(self, location: tuple[float, float]):
        """
        Get the address based on a (lat, long) tuple.

        This function is used as a sync wrapper to the Nominatim API
        """

        try:
            result = self.nominatim.query(*location, reverse=True, zoom=16)
            return result
        except Exception as exception:  # pylint: disable=broad-except
            _LOGGER.error("Failed to perform reverse geocoding - %s", exception)
            return None

    def get_matrix(self, origin: tuple[float, float], destination: tuple[float, float]):
        try:
            result = self._gmaps_client.distance_matrix(
                origins=[origin],
                destinations=[destination],
                mode="driving",
                departure_time=datetime.now(),
            )
            return result["rows"][0]["elements"][0]
        except Exception as exception:  # pylint: disable=broad-except
            _LOGGER.error("Failed to get distances - %s", exception)
            return None

    def get_data(
        self, origin: tuple[float, float], destination: tuple[float, float]
    ) -> JourneyData:
        return JourneyData(
            self.get_address(origin), self.get_matrix(origin, destination)
        )

    async def async_get_data(
        self, origin: tuple[float, float], destination: tuple[float, float]
    ) -> JourneyData:
        """
        Asychronous function to poll the APIs
        """
        return await asyncio.get_event_loop().run_in_executor(
            None, self.get_data, origin, destination
        )

    async def test_credentials(self) -> bool:
        """Check the Google Maps API credentials"""

        def test_api():
            try:
                self._gmaps_client.distance_matrix(
                    origins=[(51.478, 0)], destinations=[(51.748, 0.02)], mode="driving"
                )
            except Exception as ex:
                _LOGGER.error("Failed to validate credentials - %s", ex)
                raise

        return await asyncio.get_event_loop().run_in_executor(None, test_api)

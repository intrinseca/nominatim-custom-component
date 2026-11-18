"""Nominatim API Client."""

import asyncio
import logging
from collections import OrderedDict
from typing import cast

from geopy.adapters import AioHTTPAdapter
from geopy.exc import GeocoderRateLimited, GeocoderTimedOut, GeocoderUnavailable
from geopy.geocoders import Nominatim

_LOGGER: logging.Logger = logging.getLogger(__package__)


Coordinates = tuple[float, float]
REQUEST_TIMEOUT = 15
MAX_ATTEMPTS = 3


class CacheDict(OrderedDict):
    """Dict with a limited length, ejecting LRUs as needed."""

    def __init__(self, *args, cache_len: int = 10, **kwargs):
        """Create a LRU cache dictionary."""
        assert cache_len > 0
        self.cache_len = cache_len

        super().__init__(*args, **kwargs)

    def __setitem__(self, key, value):
        """Add/update an item in the cache."""
        super().__setitem__(key, value)
        super().move_to_end(key)

        while len(self) > self.cache_len:
            oldkey = next(iter(self))
            super().__delitem__(oldkey)

    def __getitem__(self, key):
        """Get an item from the cache."""
        val = super().__getitem__(key)
        super().move_to_end(key)

        return val


nominatim_cache = CacheDict(cache_len=256)


def round_coordinates(coordinates: Coordinates) -> Coordinates:
    """Round lat/long to 4 decimal places, or approximately 10m."""
    return cast(Coordinates, tuple(round(i, 4) for i in coordinates))


class NominatimApiClient:
    """API client for the OSM Nominatim and Google Travel Time APIs."""

    def __init__(self, osm_username: str) -> None:
        """Initialise the API client."""
        self._osm_username = osm_username

        self.nominatim = Nominatim(
            user_agent=f"Nominatim Home Assistant Integration ({self._osm_username})",
            adapter_factory=AioHTTPAdapter,
            timeout=REQUEST_TIMEOUT,
        )

    async def async_get_address(self, location: Coordinates):
        """Get address corresponding to location using OSM."""
        try:
            location = round_coordinates(location)

            if (address := nominatim_cache.get(location)) is None:
                _LOGGER.debug("Cache miss, looking up from API")
                for attempt in range(MAX_ATTEMPTS):
                    try:
                        address = await self.nominatim.reverse(
                            f"{location[0]}, {location[1]}", zoom=16
                        )
                        break
                    except (
                        GeocoderTimedOut,
                        GeocoderUnavailable,
                        GeocoderRateLimited,
                    ) as error:
                        if attempt == MAX_ATTEMPTS - 1:
                            raise
                        delay = 2**attempt
                        if isinstance(error, GeocoderRateLimited):
                            delay = max(delay, error.retry_after or 0)
                        _LOGGER.warning(
                            "Reverse geocoding failed; retrying in %s seconds: %s",
                            delay,
                            error,
                        )
                        await asyncio.sleep(delay)
                nominatim_cache[location] = address

            return address
        except Exception as exception:  # pylint: disable=broad-except
            _LOGGER.error("Failed to perform reverse geocoding - %s", exception)
            raise

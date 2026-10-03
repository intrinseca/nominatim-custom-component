"""Tests for the geopy API client and cache."""

from unittest.mock import AsyncMock, patch

import pytest
from geopy.adapters import AioHTTPAdapter
from geopy.location import Location

from custom_components.nominatim.api import (
    CacheDict,
    NominatimApiClient,
    nominatim_cache,
    round_coordinates,
)


def test_cache_eviction_and_recency():
    """Keep the most recently accessed entries."""
    cache = CacheDict(cache_len=2)
    cache["a"] = 1
    cache["b"] = 2
    assert cache["a"] == 1
    cache["c"] = 3
    assert list(cache) == ["a", "c"]
    cache["a"] = 4
    assert list(cache) == ["c", "a"]


def test_cache_requires_positive_size():
    """Reject empty caches."""
    with pytest.raises(AssertionError):
        CacheDict(cache_len=0)


def test_round_coordinates():
    """Round coordinates to the precision used for reverse lookups."""
    assert round_coordinates((51.500012, -0.120012)) == (51.5, -0.12)


def test_geopy_async_adapter():
    """The pinned geopy version accepts the integration's async adapter."""
    client = NominatimApiClient("example")
    assert client.nominatim.adapter.__class__ is AioHTTPAdapter


@pytest.mark.asyncio
async def test_reverse_lookup_and_cache():
    """Look up rounded coordinates once and return the cached Location."""
    nominatim_cache.clear()
    address = Location("London", (51.5, -0.12), {"address": {"city": "London"}})
    with patch("custom_components.nominatim.api.Nominatim") as geocoder:
        geocoder.return_value.reverse = AsyncMock(return_value=address)
        client = NominatimApiClient("example")
        assert "example" in geocoder.call_args.kwargs["user_agent"]
        assert await client.async_get_address((51.500012, -0.120012)) is address
        assert await client.async_get_address((51.500022, -0.120022)) is address
        geocoder.return_value.reverse.assert_awaited_once_with("51.5, -0.12", zoom=16)
    nominatim_cache.clear()


@pytest.mark.asyncio
async def test_lookup_failure_is_propagated():
    """Do not cache a failed lookup."""
    nominatim_cache.clear()
    with patch("custom_components.nominatim.api.Nominatim") as geocoder:
        geocoder.return_value.reverse = AsyncMock(side_effect=RuntimeError("offline"))
        client = NominatimApiClient("example")
        with pytest.raises(RuntimeError, match="offline"):
            await client.async_get_address((1, 2))
        assert (1, 2) not in nominatim_cache

"""Tests for setup, coordinator, configuration, and sensor behavior."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from geopy.location import Location
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.nominatim import (
    NominatimData,
    NominatimDataUpdateCoordinator,
    async_reload_entry,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.nominatim.config_flow import NominatimFlowHandler
from custom_components.nominatim.const import (
    ATTRIBUTION,
    CONF_OSM_USERNAME,
    CONF_SOURCE,
    DOMAIN,
)
from custom_components.nominatim.sensor import (
    NominatimLocationSensor,
    async_setup_entry as async_setup_sensor,
)


@pytest.fixture
def hass():
    """Provide only the HA state and config entry interfaces used here."""
    result = SimpleNamespace(data={}, config_entries=SimpleNamespace())
    result.states = SimpleNamespace(
        get=Mock(return_value=SimpleNamespace(state="home", name="Tracker"))
    )
    result.config_entries.async_forward_entry_setups = AsyncMock()
    result.config_entries.async_forward_entry_unload = AsyncMock(return_value=True)
    return result


@pytest.fixture
def entry():
    """Provide an integration config entry."""
    return SimpleNamespace(
        entry_id="entry-1",
        data={CONF_OSM_USERNAME: "example", CONF_SOURCE: "device_tracker.phone"},
        add_update_listener=Mock(),
    )


@pytest.fixture
def address():
    """Provide a geopy Location with an address."""
    return Location(
        "London", (51.5, -0.12), {"address": {"city": "London", "country": "UK"}}
    )


@pytest.mark.asyncio
async def test_setup_and_unload(hass, entry):
    """Register the coordinator, forward the platform, and clean up on unload."""
    with patch("custom_components.nominatim.NominatimApiClient") as client:
        assert await async_setup_entry(hass, entry)
        client.assert_called_once_with("example")
        assert isinstance(
            hass.data[DOMAIN][entry.entry_id], NominatimDataUpdateCoordinator
        )
        hass.config_entries.async_forward_entry_setups.assert_awaited_once()
        entry.add_update_listener.assert_called_once_with(async_reload_entry)
        assert await async_unload_entry(hass, entry)
        assert entry.entry_id not in hass.data[DOMAIN]


@pytest.mark.asyncio
async def test_failed_unload_preserves_coordinator(hass, entry):
    """Leave the coordinator available if a platform cannot unload."""
    hass.data[DOMAIN] = {entry.entry_id: object()}
    hass.config_entries.async_forward_entry_unload.return_value = False
    assert not await async_unload_entry(hass, entry)
    assert entry.entry_id in hass.data[DOMAIN]


@pytest.mark.asyncio
async def test_reload(hass, entry):
    """Reload by unloading and setting up again."""
    with patch("custom_components.nominatim.NominatimApiClient"):
        await async_setup_entry(hass, entry)
        await async_reload_entry(hass, entry)
        assert entry.entry_id in hass.data[DOMAIN]


@pytest.mark.asyncio
async def test_coordinator_update(hass, address):
    """Resolve a tracker position into a geopy location."""
    client = SimpleNamespace(async_get_address=AsyncMock(return_value=address))
    coordinator = NominatimDataUpdateCoordinator(hass, client, "device_tracker.phone")
    with patch(
        "custom_components.nominatim.find_coordinates", return_value="51.5,-0.12"
    ):
        result = await coordinator.update()
    assert result.origin_address == "London"
    client.async_get_address.assert_awaited_once_with((51.5, -0.12))


@pytest.mark.asyncio
@pytest.mark.parametrize("coordinates", [None, "invalid", "not-a-number,2"])
async def test_coordinator_rejects_invalid_coordinates(hass, coordinates):
    """Turn missing and malformed coordinates into update failures."""
    client = SimpleNamespace(async_get_address=AsyncMock())
    coordinator = NominatimDataUpdateCoordinator(hass, client, "device_tracker.phone")
    with (
        patch("custom_components.nominatim.find_coordinates", return_value=coordinates),
        pytest.raises(UpdateFailed, match="Unable to find coordinates"),
    ):
        await coordinator.update()
    client.async_get_address.assert_not_awaited()


@pytest.mark.asyncio
async def test_coordinator_propagates_api_error(hass):
    """Wrap API failures as update failures."""
    client = SimpleNamespace(
        async_get_address=AsyncMock(side_effect=RuntimeError("offline"))
    )
    coordinator = NominatimDataUpdateCoordinator(hass, client, "device_tracker.phone")
    with (
        patch("custom_components.nominatim.find_coordinates", return_value="1,2"),
        pytest.raises(UpdateFailed, match="offline"),
    ):
        await coordinator.update()


@pytest.mark.asyncio
async def test_state_changes_choose_refresh(hass):
    """Force an update on changed states or first data, debounce later ones."""
    coordinator = NominatimDataUpdateCoordinator(hass, Mock(), "device_tracker.phone")
    coordinator.async_refresh = AsyncMock()
    coordinator.async_request_refresh = AsyncMock()
    same = SimpleNamespace(
        data={
            "old_state": SimpleNamespace(state="home"),
            "new_state": SimpleNamespace(state="home"),
        }
    )
    changed = SimpleNamespace(
        data={
            "old_state": SimpleNamespace(state="home"),
            "new_state": SimpleNamespace(state="away"),
        }
    )
    await coordinator._handle_origin_state_change(same)
    coordinator.data = object()
    await coordinator._handle_origin_state_change(same)
    await coordinator._handle_origin_state_change(changed)
    assert coordinator.async_refresh.await_count == 2
    coordinator.async_request_refresh.assert_awaited_once()


def test_address_fallbacks(address):
    """Pick the most local address name and fall back when unavailable."""
    assert NominatimData(address).origin_address == "London"
    assert NominatimData(None).origin_address == "Unknown"
    assert (
        NominatimData(Location("Unknown", (0, 0), {"address": {}})).origin_address
        == "Unknown"
    )


@pytest.mark.asyncio
async def test_config_flow():
    """Display the form and create an entry from user input."""
    flow = NominatimFlowHandler()
    form = await flow.async_step_user()
    assert form["step_id"] == "user"
    assert form["data_schema"](
        {CONF_SOURCE: "device_tracker.phone", CONF_OSM_USERNAME: "example"}
    )
    data = {CONF_SOURCE: "device_tracker.phone", CONF_OSM_USERNAME: "example"}
    assert await flow.async_step_user(data) == {
        "title": "device_tracker.phone Nominatim",
        "data": data,
    }


@pytest.mark.asyncio
async def test_sensor_setup_and_state(hass, entry, address):
    """Expose the geocoded address and attribution on the sensor."""
    coordinator = SimpleNamespace(data=NominatimData(address))
    hass.data[DOMAIN] = {entry.entry_id: coordinator}
    add_entities = Mock()
    await async_setup_sensor(hass, entry, add_entities)
    sensor = add_entities.call_args.args[0][0]
    assert isinstance(sensor, NominatimLocationSensor)
    assert sensor._attr_name == "Tracker Current Location"
    assert sensor._attr_unique_id == "entry-1-location"
    assert sensor.state == "London"
    assert sensor.extra_state_attributes == {
        "city": "London",
        "country": "UK",
        "attribution": ATTRIBUTION,
    }
    coordinator.data = None
    assert sensor.state is None
    assert sensor.extra_state_attributes == {}
    coordinator.data = NominatimData(None)
    assert sensor.extra_state_attributes == {}

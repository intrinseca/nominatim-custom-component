"""Sensor platform for Nominatim."""

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NominatimData
from .const import ATTRIBUTION, CONF_SOURCE, DOMAIN, ICON


async def async_setup_entry(hass, entry, async_add_devices):
    """Set up sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    source_name = hass.states.get(entry.data.get(CONF_SOURCE)).name

    async_add_devices(
        [
            NominatimLocationSensor(coordinator, entry, source_name),
        ]
    )


class NominatimLocationSensor(CoordinatorEntity[NominatimData]):  # type: ignore
    """Nominatim Location Sensor class."""

    def __init__(self, coordinator, config_entry, source_name):
        """Create location sensor."""
        super().__init__(coordinator)

        self._attr_name = f"{source_name} Current Location"
        self._attr_icon = ICON
        self._attr_unique_id = config_entry.entry_id + "-location"

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if (
            self.coordinator.data is not None
            and self.coordinator.data.origin_reverse_geocode is not None
        ):
            return self.coordinator.data.origin_reverse_geocode.raw["address"] | {
                "attribution": ATTRIBUTION,
            }
        else:
            return {}

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data.origin_address
        else:
            return None

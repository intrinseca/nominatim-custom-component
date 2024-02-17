"""Sensor platform for Nominatim."""

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NominatimData
from .const import ATTRIBUTION, CONF_NAME, DOMAIN, ICON


async def async_setup_entry(hass, entry, async_add_devices):
    """Set up sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_devices(
        [
            NominatimLocationSensor(coordinator, entry),
        ]
    )


class NominatimLocationSensor(CoordinatorEntity[NominatimData]):  # type: ignore
    """Nominatim Location Sensor class."""

    def __init__(self, coordinator, config_entry):
        """Create location sensor."""
        super().__init__(coordinator)
        self.config_entry = config_entry

    @property
    def unique_id(self):
        """Return a unique ID to use for this entity."""
        return self.config_entry.entry_id + "-location"

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
    def name(self):
        """Return the name of the sensor."""
        name = self.config_entry.data.get(CONF_NAME)

        return f"{name} Current Location"

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data.origin_address
        else:
            return None

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICON

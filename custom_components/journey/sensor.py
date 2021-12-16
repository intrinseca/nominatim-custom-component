"""Sensor platform for Journey."""
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME
from .const import DOMAIN
from .const import ICON
from .const import SENSOR
from .const import ATTRIBUTION


async def async_setup_entry(hass, entry, async_add_devices):
    """Setup sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_devices([JourneySensor(coordinator, entry)])


class JourneySensor(CoordinatorEntity):
    """journey Sensor class."""

    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator)
        self.config_entry = config_entry

    @property
    def unique_id(self):
        """Return a unique ID to use for this entity."""
        return self.config_entry.entry_id

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "attribution": ATTRIBUTION,
            "full_address": self.coordinator.data.displayName(),
        }

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{DEFAULT_NAME}_{SENSOR}"

    @property
    def state(self):
        """Return the state of the sensor."""
        address = self.coordinator.data.address()

        for key in ["village", "suburb", "town", "city", "state", "country"]:
            if key in address:
                return address[key]

        return "Unknown"

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICON

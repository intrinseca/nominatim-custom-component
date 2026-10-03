"""Small Home Assistant stand-ins for isolated unit tests.

These tests exercise the integration's logic without starting Home Assistant.
"""

import sys
from types import ModuleType


def module(name):
    """Register a module and link it to its parent."""
    result = ModuleType(name)
    sys.modules[name] = result
    if "." in name:
        parent, attribute = name.rsplit(".", 1)
        setattr(sys.modules[parent], attribute, result)
    return result


homeassistant = module("homeassistant")
config_entries = module("homeassistant.config_entries")
core = module("homeassistant.core")
helpers = module("homeassistant.helpers")
debounce = module("homeassistant.helpers.debounce")
event = module("homeassistant.helpers.event")
location = module("homeassistant.helpers.location")
update_coordinator = module("homeassistant.helpers.update_coordinator")


class ConfigFlow:
    """Model the methods used by the config flow."""

    def __init_subclass__(cls, **kwargs):
        """Accept Home Assistant's domain keyword."""
        super().__init_subclass__()

    def async_create_entry(self, **kwargs):
        """Return the entry result."""
        return kwargs

    def async_show_form(self, **kwargs):
        """Return the form result."""
        return kwargs


class DataUpdateCoordinator:
    """Keep the attributes the integration uses."""

    def __class_getitem__(cls, item):
        """Support the generic annotation."""
        return cls

    def __init__(self, hass, logger, **kwargs):
        """Initialize the coordinator."""
        self.hass = hass
        self.data = None

    async def async_refresh(self):
        """Stand in for a forced refresh."""

    async def async_request_refresh(self):
        """Stand in for a debounced refresh."""


class CoordinatorEntity:
    """Keep the entity's coordinator reference."""

    def __class_getitem__(cls, item):
        """Support the generic annotation."""
        return cls

    def __init__(self, coordinator):
        """Initialize the entity."""
        self.coordinator = coordinator


class UpdateFailed(Exception):
    """Stand in for a coordinator update failure."""


config_entries.ConfigEntry = type("ConfigEntry", (), {})
config_entries.ConfigFlow = ConfigFlow
config_entries.CONN_CLASS_CLOUD_POLL = "cloud_poll"
core.Event = type("Event", (), {})
core.HomeAssistant = type("HomeAssistant", (), {})
debounce.Debouncer = lambda *args, **kwargs: None
event.async_track_state_change_event = lambda *args: None
location.find_coordinates = lambda *args: None
update_coordinator.DataUpdateCoordinator = DataUpdateCoordinator
update_coordinator.CoordinatorEntity = CoordinatorEntity
update_coordinator.UpdateFailed = UpdateFailed

"""Helpers for handling location entities."""
import logging

from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.helpers import location

_LOGGER: logging.Logger = logging.getLogger(__package__)


def get_location_entity(hass, entity_id):
    """Get the location from the entity state or attributes."""

    if (entity := hass.states.get(entity_id)) is None:
        _LOGGER.error("Locating %s: Unable to find", entity_id)
        raise ValueError("Invalid entity ID")

    # Check if device is in a zone
    if not entity_id.startswith("zone"):
        if (zone_entity := hass.states.get(f"zone.{entity.state}")) is not None:
            if location.has_location(zone_entity):
                _LOGGER.debug(
                    "Locating %s: in %s, getting zone location",
                    entity_id,
                    zone_entity.entity_id,
                )
                return zone_entity

            _LOGGER.debug(
                "Locating %s: in %s, no zone location",
                entity_id,
                zone_entity.entity_id,
            )
        else:
            _LOGGER.debug("Locating %s: [zone '%s' not found]", entity_id, entity.state)

    # Check if the entity has location attributes
    if location.has_location(entity):
        _LOGGER.debug("Locating %s: from attributes", entity_id)
        return entity

    # When everything fails just return nothing
    return None


def get_location_from_attributes(entity):
    """Get the lat/long string from an entities attributes."""
    attr = entity.attributes
    return (float(attr.get(ATTR_LATITUDE)), float(attr.get(ATTR_LONGITUDE)))


def get_location_from_entity(hass, entity_id):
    """Get the location from the entity state or attributes."""

    return get_location_from_attributes(get_location_entity(hass, entity_id))

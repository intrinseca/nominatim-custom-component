"""Constants for Journey."""
# Base component constants

NAME = "Journey"
DOMAIN = "journey"
DOMAIN_DATA = f"{DOMAIN}_data"
VERSION = "0.1.0"

ATTRIBUTION = "Map data © OpenStreetMap contributors"
ISSUE_URL = "https://github.com/intrinseca/journey/issues"

# Icons
ICON = "mdi:map-marker-right"

# Platforms
SENSOR = "sensor"
PLATFORMS = [SENSOR]

# Configuration and options
CONF_ENABLED = "enabled"
CONF_NAME = "name"
CONF_OSM_USERNAME = "osm_username"
CONF_GMAPS_TOKEN = "gmaps_token"
CONF_ORIGIN = "origin"
CONF_DESTINATION = "destination"

# Defaults
DEFAULT_NAME = DOMAIN


STARTUP_MESSAGE = f"""
-------------------------------------------------------------------
{NAME}
Version: {VERSION}
This is a custom integration!
If you have any issues with this you need to open an issue here:
{ISSUE_URL}
-------------------------------------------------------------------
"""

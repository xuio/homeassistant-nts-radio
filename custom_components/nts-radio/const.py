"""Constants for the NTS Radio integration."""

DOMAIN = "nts_radio"
CONF_UPDATE_INTERVAL = "update_interval"
DEFAULT_UPDATE_INTERVAL = 60  # seconds

API_URL = "https://www.nts.live/api/v2/live"
DEFAULT_TIMEOUT = 10

ATTR_SHOW_NAME = "show_name"
ATTR_DESCRIPTION = "description"
ATTR_LOCATION = "location"
ATTR_GENRES = "genres"
ATTR_START_TIME = "start_time"
ATTR_END_TIME = "end_time"
ATTR_IMAGE_URL = "image_url"
ATTR_IS_REPLAY = "is_replay"
ATTR_NEXT_SHOW = "next_show"
ATTR_NEXT_START_TIME = "next_start_time"

SENSOR_TYPES = {
    "channel_1": {
        "name": "NTS Channel 1",
        "icon": "mdi:radio",
    },
    "channel_2": {
        "name": "NTS Channel 2",
        "icon": "mdi:radio",
    },
}

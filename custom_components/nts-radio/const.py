"""Constants for the NTS Radio integration."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "nts_radio"

# Config flow
CONF_UPDATE_INTERVAL = "update_interval"
CONF_EMAIL = "email"
CONF_PASSWORD = "password"

# Default values
DEFAULT_UPDATE_INTERVAL = 50  # seconds
MIN_UPDATE_INTERVAL = 10
MAX_UPDATE_INTERVAL = 300
DEFAULT_TIMEOUT = 30  # seconds

# Firebase configuration from decompiled app
FIREBASE_CONFIG = {
    "apiKey": "AIzaSyA4Qp5AvHC8Rev72-10-_DY614w_bxUCJU",
    "authDomain": "nts-ios-app.firebaseapp.com",
    "databaseURL": "https://nts-ios-app.firebaseio.com",
    "projectId": "nts-ios-app",
    "storageBucket": "nts-ios-app.appspot.com",
    "messagingSenderId": "52151881343",
    "appId": "1:52151881343:ios:6a6dcf3c4ea30c0bbbc7f3",
}

# API
API_TIMEOUT = 10  # seconds

# Channel IDs
CHANNEL_1 = 1
CHANNEL_2 = 2

# API endpoints
API_URL = "https://www.nts.live/api/v2/live"

# Attributes
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

# Track attributes
ATTR_CURRENT_TRACK = "current_track"
ATTR_TRACK_ARTIST = "track_artist"
ATTR_TRACK_TITLE = "track_title"
ATTR_TRACK_START_TIME = "track_start_time"
ATTR_RECENT_TRACKS = "recent_tracks"
ATTR_AUTHENTICATED = "authenticated"

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

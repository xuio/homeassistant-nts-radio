"""Support for NTS Radio sensors."""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_AUTHENTICATED,
    ATTR_CURRENT_TRACK,
    ATTR_DESCRIPTION,
    ATTR_END_TIME,
    ATTR_GENRES,
    ATTR_IMAGE_URL,
    ATTR_IS_REPLAY,
    ATTR_LOCATION,
    ATTR_NEXT_SHOW,
    ATTR_NEXT_START_TIME,
    ATTR_RECENT_TRACKS,
    ATTR_SHOW_NAME,
    ATTR_START_TIME,
    ATTR_TRACK_ARTIST,
    ATTR_TRACK_START_TIME,
    ATTR_TRACK_TITLE,
    DOMAIN,
    SENSOR_TYPES,
)
from .coordinator import NTSRadioDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up NTS Radio sensors from a config entry."""
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = entry_data["coordinator"]
    live_tracks_handler = entry_data.get("live_tracks_handler")
    has_live_tracks = live_tracks_handler is not None

    sensors = []

    # Create sensors for each channel
    for sensor_type, sensor_config in SENSOR_TYPES.items():
        channel_num = sensor_type.split("_")[1]

        # Main sensor - current playing
        sensors.append(
            NTSRadioSensor(
                coordinator,
                sensor_type,
                sensor_config["name"],
                sensor_config["icon"],
                has_live_tracks,
            )
        )

        # Next show sensor
        sensors.append(
            NTSNextShowSensor(
                coordinator,
                sensor_type,
                f"NTS Channel {channel_num} - Next Show",
                "mdi:skip-next",
            )
        )

        # Current track sensor (only if authentication is available)
        if has_live_tracks:
            sensors.append(
                NTSCurrentTrackSensor(
                    coordinator,
                    sensor_type,
                    f"NTS Channel {channel_num} - Track ID",
                    "mdi:music-note",
                )
            )

    async_add_entities(sensors, True)


class NTSRadioBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for NTS Radio sensors."""

    def __init__(
        self,
        coordinator: NTSRadioDataUpdateCoordinator,
        sensor_type: str,
        name: str,
        icon: str,
        unique_id_suffix: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._sensor_type = sensor_type
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{DOMAIN}_{sensor_type}_{unique_id_suffix}"

        # Extract channel number for device info
        self._channel_num = sensor_type.split("_")[1]

        # Set device info to group sensors by channel
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"channel_{self._channel_num}")},
            name=f"NTS Channel {self._channel_num}",
            manufacturer="NTS Radio",
            model="Live Stream",
            sw_version="1.0",
        )

    @property
    def channel_data(self) -> Optional[Dict[str, Any]]:
        """Get channel data from coordinator."""
        if self.coordinator.data and self._sensor_type in self.coordinator.data:
            return self.coordinator.data[self._sensor_type]
        return None


class NTSRadioSensor(NTSRadioBaseSensor):
    """Main NTS Radio sensor showing current playing."""

    def __init__(
        self,
        coordinator: NTSRadioDataUpdateCoordinator,
        sensor_type: str,
        name: str,
        icon: str,
        has_live_tracks: bool,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, sensor_type, name, icon, "now_playing")
        self._has_live_tracks = has_live_tracks

    @property
    def native_value(self) -> Optional[str]:
        """Return the state of the sensor."""
        channel_data = self.channel_data
        if not channel_data:
            return "No show currently playing"

        # Always show the broadcast title (show name)
        now = channel_data.get("now", {})
        broadcast_title = now.get("broadcast_title", "No show currently playing")
        if broadcast_title and broadcast_title.endswith(" (R)"):
            # Remove the (R) from the display
            return broadcast_title[:-4]
        return broadcast_title

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes."""
        attributes = {}
        channel_data = self.channel_data

        if not channel_data:
            return attributes

        now = channel_data.get("now", {})

        # Current show details
        embeds = now.get("embeds", {})
        details = embeds.get("details", {})

        attributes[ATTR_SHOW_NAME] = now.get("broadcast_title", "Unknown")
        attributes[ATTR_IS_REPLAY] = " (R)" in now.get("broadcast_title", "")

        if details:
            attributes[ATTR_DESCRIPTION] = details.get("description", "")
            attributes[ATTR_LOCATION] = details.get("location_long", "")

            # Extract genres
            genres = details.get("genres", [])
            if genres:
                attributes[ATTR_GENRES] = ", ".join(
                    [g.get("value", "") for g in genres]
                )
            else:
                attributes[ATTR_GENRES] = ""

            # Get image URL
            media = details.get("media", {})
            if media:
                attributes[ATTR_IMAGE_URL] = media.get("picture_medium", "")

        # Time information
        start_time = now.get("start_timestamp")
        end_time = now.get("end_timestamp")

        if start_time:
            attributes[ATTR_START_TIME] = start_time
        if end_time:
            attributes[ATTR_END_TIME] = end_time

        # Authentication status
        attributes[ATTR_AUTHENTICATED] = self._has_live_tracks

        # Recent tracks if available
        recent_tracks = channel_data.get("recent_tracks", [])
        if recent_tracks:
            attributes[ATTR_RECENT_TRACKS] = recent_tracks

        return attributes

    @property
    def entity_picture(self) -> Optional[str]:
        """Return the entity picture."""
        channel_data = self.channel_data
        if not channel_data:
            return None

        now = channel_data.get("now", {})
        embeds = now.get("embeds", {})
        details = embeds.get("details", {})
        media = details.get("media", {})
        if media:
            return media.get("picture_small")
        return None


class NTSNextShowSensor(NTSRadioBaseSensor):
    """Sensor showing the next scheduled show."""

    def __init__(
        self,
        coordinator: NTSRadioDataUpdateCoordinator,
        sensor_type: str,
        name: str,
        icon: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, sensor_type, name, icon, "next_show")

    @property
    def native_value(self) -> Optional[str]:
        """Return the next show name."""
        channel_data = self.channel_data
        if not channel_data:
            return "Unknown"

        next_show = channel_data.get("next", {})
        broadcast_title = next_show.get("broadcast_title", "Unknown")

        # Remove (R) suffix if present
        if broadcast_title.endswith(" (R)"):
            return broadcast_title[:-4]
        return broadcast_title

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes."""
        attributes = {}
        channel_data = self.channel_data

        if not channel_data:
            return attributes

        next_show = channel_data.get("next", {})

        # Add start time
        start_time = next_show.get("start_timestamp")
        if start_time:
            attributes["start_time"] = start_time

        # Add end time
        end_time = next_show.get("end_timestamp")
        if end_time:
            attributes["end_time"] = end_time

        # Check if it's a replay
        broadcast_title = next_show.get("broadcast_title", "")
        attributes["is_replay"] = " (R)" in broadcast_title

        # Get next show details if available
        embeds = next_show.get("embeds", {})
        details = embeds.get("details", {})
        if details:
            media = details.get("media", {})
            if media:
                attributes["image_url"] = media.get("picture_medium", "")

        return attributes

    @property
    def entity_picture(self) -> Optional[str]:
        """Return the entity picture for next show."""
        channel_data = self.channel_data
        if not channel_data:
            return None

        next_show = channel_data.get("next", {})
        embeds = next_show.get("embeds", {})
        details = embeds.get("details", {})
        media = details.get("media", {})
        if media:
            return media.get("picture_small")
        return None


class NTSCurrentTrackSensor(NTSRadioBaseSensor):
    """Sensor showing the current track (when authenticated)."""

    def __init__(
        self,
        coordinator: NTSRadioDataUpdateCoordinator,
        sensor_type: str,
        name: str,
        icon: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, sensor_type, name, icon, "track_id")

    @property
    def native_value(self) -> Optional[str]:
        """Return the current track title."""
        channel_data = self.channel_data
        if not channel_data:
            return "No track info"

        current_track = channel_data.get("current_track")
        if current_track:
            # Return combined artist - title as track ID
            artist = current_track.get("artists", "")
            title = current_track.get("title", "")

            # Format the display string
            if artist and title:
                return f"{artist} - {title}"
            elif title:
                return title
            elif artist:
                return artist
            else:
                # If we have a track but no info, show placeholder
                return "Unknown Track"

        # Return show name if no track info
        now = channel_data.get("now", {})
        return now.get("broadcast_title", "No track info")

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes."""
        attributes = {}
        channel_data = self.channel_data

        if not channel_data:
            return attributes

        current_track = channel_data.get("current_track")
        if current_track:
            artist = current_track.get("artists", "")
            title = current_track.get("title", "")

            if artist:
                attributes["artist"] = artist
            if title:
                attributes["title"] = title
            if current_track.get("start_time"):
                attributes["start_time"] = current_track.get("start_time")

            # Add track position in recent tracks
            recent_tracks = channel_data.get("recent_tracks", [])
            if recent_tracks and len(recent_tracks) > 0:
                attributes["track_number"] = 1  # Current track is always first
                attributes["total_recent_tracks"] = len(recent_tracks)
        else:
            # If no track info, indicate it's showing show info
            attributes["info_type"] = "show"
            now = channel_data.get("now", {})
            attributes["show_name"] = now.get("broadcast_title", "Unknown")

        return attributes

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Always available, will show show info if no track data
        return self.coordinator.last_update_success

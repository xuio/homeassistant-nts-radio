"""Support for NTS Radio sensors."""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_DESCRIPTION,
    ATTR_END_TIME,
    ATTR_GENRES,
    ATTR_IMAGE_URL,
    ATTR_IS_REPLAY,
    ATTR_LOCATION,
    ATTR_NEXT_SHOW,
    ATTR_NEXT_START_TIME,
    ATTR_SHOW_NAME,
    ATTR_START_TIME,
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
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    sensors = []
    for sensor_type, sensor_config in SENSOR_TYPES.items():
        sensors.append(
            NTSRadioSensor(
                coordinator,
                sensor_type,
                sensor_config["name"],
                sensor_config["icon"],
            )
        )

    async_add_entities(sensors, True)


class NTSRadioSensor(CoordinatorEntity, SensorEntity):
    """Representation of an NTS Radio sensor."""

    def __init__(
        self,
        coordinator: NTSRadioDataUpdateCoordinator,
        sensor_type: str,
        name: str,
        icon: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._sensor_type = sensor_type
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{DOMAIN}_{sensor_type}"

    @property
    def native_value(self) -> Optional[str]:
        """Return the state of the sensor."""
        if self.coordinator.data and self._sensor_type in self.coordinator.data:
            channel_data = self.coordinator.data[self._sensor_type]
            now = channel_data.get("now", {})

            # Check if it's a replay by looking for (R) in the title
            broadcast_title = now.get("broadcast_title", "No show currently playing")
            if broadcast_title and broadcast_title.endswith(" (R)"):
                # Remove the (R) from the display
                return broadcast_title[:-4]
            return broadcast_title
        return "No show currently playing"

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes."""
        attributes = {}

        if self.coordinator.data and self._sensor_type in self.coordinator.data:
            channel_data = self.coordinator.data[self._sensor_type]
            now = channel_data.get("now", {})
            next_show = channel_data.get("next", {})

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

            # Next show information
            if next_show:
                attributes[ATTR_NEXT_SHOW] = next_show.get("broadcast_title", "Unknown")
                attributes[ATTR_NEXT_START_TIME] = next_show.get("start_timestamp", "")

        return attributes

    @property
    def entity_picture(self) -> Optional[str]:
        """Return the entity picture."""
        if self.coordinator.data and self._sensor_type in self.coordinator.data:
            channel_data = self.coordinator.data[self._sensor_type]
            now = channel_data.get("now", {})
            embeds = now.get("embeds", {})
            details = embeds.get("details", {})
            media = details.get("media", {})
            if media:
                return media.get("picture_small")
        return None

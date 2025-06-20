"""NTS Radio – Binary Sensor platform.

Provides a per-channel binary sensor that indicates whether the currently
playing show is in the authenticated user's favourites list.  The entity's
state is `on` when the current show *is* favourited, otherwise `off`.  The
attributes expose the complete list of favourite shows by title.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SENSOR_TYPES
from .coordinator import NTSRadioDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up NTS Radio binary sensors from a config entry."""

    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator: NTSRadioDataUpdateCoordinator = entry_data["coordinator"]
    has_favourites = bool(entry_data.get("live_tracks_handler"))

    if not has_favourites:
        _LOGGER.debug("NTS Radio: favourites not enabled – skipping binary sensors")
        return

    entities: list[NTSFavouriteSensor] = []
    for sensor_type in SENSOR_TYPES.keys():
        channel_num = sensor_type.split("_")[1]
        entities.append(
            NTSFavouriteSensor(
                coordinator,
                sensor_type,
                f"NTS Channel {channel_num} – Favourite",
                "mdi:heart",
            )
        )

    async_add_entities(entities, True)


class NTSFavouriteSensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor that is `on` when the current show is favourited."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: NTSRadioDataUpdateCoordinator,
        sensor_type: str,
        name: str,
        icon: str,
    ) -> None:
        super().__init__(coordinator)
        self._sensor_type = sensor_type
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{DOMAIN}_{sensor_type}_fav"

        # Extract channel number for nice device grouping
        self._channel_num = sensor_type.split("_")[1]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"channel_{self._channel_num}")},
            name=f"NTS Channel {self._channel_num}",
            manufacturer="NTS Radio",
            model="Live Stream",
            sw_version="1.0",
        )

    # ---------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------

    @property
    def _channel_data(self) -> Optional[Dict[str, Any]]:
        if self.coordinator.data and self._sensor_type in self.coordinator.data:
            return self.coordinator.data[self._sensor_type]
        return None

    @property
    def is_on(self) -> bool | None:  # type: ignore[override]
        """Return True if current show is in favourites."""
        channel_data = self._channel_data
        if not channel_data:
            return None

        now = channel_data.get("now", {})
        details = now.get("embeds", {}).get("details", {})
        show_alias = details.get("show_alias")

        if not show_alias:
            return False

        favourites: List[Dict[str, Any]] = self.coordinator.data.get("favourites", []) if self.coordinator.data else []
        aliases = {fav.get("show_alias") for fav in favourites}
        _LOGGER.debug("NTS Radio: show_alias: %s", show_alias)
        _LOGGER.debug("NTS Radio: aliases: %s", aliases)
        return show_alias in aliases

    # Home Assistant 2024+ uses `extra_state_attributes` name alias
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        attributes: Dict[str, Any] = {}
        favourites: List[Dict[str, Any]] = self.coordinator.data.get("favourites", []) if self.coordinator.data else []

        fav_names: List[str] = []
        for fav in favourites:
            title = (
                fav.get("title")
                or fav.get("show_title")
                or fav.get("name")
                or fav.get("show_alias")
            )
            if title:
                fav_names.append(title)

        attributes["favourite_shows"] = fav_names
        attributes["favourites_count"] = len(fav_names)
        return attributes

"""Data update coordinator for NTS Radio."""

import asyncio
from datetime import datetime, timedelta
import html
import logging
from typing import Any, Dict, List, Optional

import aiohttp
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.helpers.event import async_track_time_change

from .live_tracks import NTSLiveTracksHandler
from .const import (
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

API_URL = "https://www.nts.live/api/v2/live"


def decode_html_entities(text: str) -> str:
    """Decode HTML entities in text."""
    if text:
        return html.unescape(text)
    return text


class NTSRadioDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching NTS Radio data."""

    def __init__(
        self,
        hass: HomeAssistant,
        update_interval: timedelta,
        live_tracks_handler: Optional[NTSLiveTracksHandler] = None,
        *,
        favourites_enabled: bool = False,
    ) -> None:
        """Initialize the data update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )
        self.live_tracks_handler = live_tracks_handler
        self._user_interval = update_interval
        self._last_scheduled_update = None

        # favourites list cache
        self.data = {}  # initialise here (super already sets but ensure type)
        if favourites_enabled:
            self.data["favourites"] = []

    async def _handle_track_update(self, channel: int, tracks: List[dict]) -> None:
        """Handle track updates from the live tracks handler."""
        _LOGGER.debug(
            "Received track update for channel %s with %s tracks", channel, len(tracks)
        )

        # Update our data with the new tracks
        if self.data:
            channel_key = f"channel_{channel}"
            if channel_key in self.data:
                current_track = tracks[0] if tracks else None
                self.data[channel_key]["current_track"] = (
                    current_track if current_track else None
                )
                self.data[channel_key]["recent_tracks"] = [
                    track for track in tracks[:10]
                ]

                # Notify listeners of the update
                self.async_set_updated_data(self.data)
                _LOGGER.info(
                    "Updated channel %s with track: %s",
                    channel,
                    current_track if current_track else "None",
                )

    async def _handle_favourites_update(self, favourites: List[dict]) -> None:
        """Handle favourites list update."""
        _LOGGER.debug("Received favourites update with %s shows", len(favourites))

        # Ensure data dict exists
        if self.data is None:
            self.data = {}

        self.data["favourites"] = favourites
        # Notify listeners
        self.async_set_updated_data(self.data)

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from NTS Radio API."""
        try:
            # Don't modify the update interval here - let the coordinator handle regular updates
            # The scheduled updates at :00 and :30 are handled separately in __init__.py
            
            _LOGGER.debug(
                "Performing periodic update. Update interval: %s seconds",
                self._user_interval.total_seconds()
            )
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    API_URL, timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)
                ) as response:
                    if response.status != 200:
                        raise UpdateFailed(f"Error fetching data: {response.status}")
                    data = await response.json()

                    # Process the data
                    processed_data = {}
                    for channel_data in data.get("results", []):
                        channel_name = channel_data.get("channel_name")
                        if channel_name:
                            channel_key = f"channel_{channel_name}"
                            
                            # Get now and next data
                            now_data = channel_data.get("now", {})
                            next_data = channel_data.get("next", {})
                            
                            # Decode HTML entities in broadcast titles
                            if "broadcast_title" in now_data:
                                now_data["broadcast_title"] = decode_html_entities(
                                    now_data["broadcast_title"]
                                )
                            if "broadcast_title" in next_data:
                                next_data["broadcast_title"] = decode_html_entities(
                                    next_data["broadcast_title"]
                                )
                            
                            # Decode HTML entities in descriptions
                            now_embeds = now_data.get("embeds", {})
                            now_details = now_embeds.get("details", {})
                            if "description" in now_details:
                                now_details["description"] = decode_html_entities(
                                    now_details["description"]
                                )
                            
                            next_embeds = next_data.get("embeds", {})
                            next_details = next_embeds.get("details", {})
                            if "description" in next_details:
                                next_details["description"] = decode_html_entities(
                                    next_details["description"]
                                )
                            
                            processed_data[channel_key] = {
                                "channel_name": channel_name,
                                "now": now_data,
                                "next": next_data,
                            }

                            # Add live track data if available
                            if (
                                self.live_tracks_handler
                                and self.live_tracks_handler.is_authenticated
                            ):
                                channel_num = int(channel_name)
                                current_track = (
                                    self.live_tracks_handler.get_current_track(
                                        channel_num
                                    )
                                )
                                recent_tracks = self.live_tracks_handler.get_tracks(
                                    channel_num
                                )

                                processed_data[channel_key]["current_track"] = (
                                    current_track if current_track else None
                                )
                                processed_data[channel_key]["recent_tracks"] = [
                                    track for track in recent_tracks[:10]
                                ]

                    # Preserve favourites list if we already have one
                    if self.data and "favourites" in self.data:
                        processed_data["favourites"] = self.data["favourites"]

                    return processed_data

        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error communicating with API: {err}")
        except Exception as err:
            raise UpdateFailed(f"Unexpected error: {err}")

    def _schedule_next_update(self) -> None:
        """Schedule the next update to align with :00 and :30 minutes."""
        # This method is no longer needed since we're handling scheduled updates separately
        # and letting the coordinator handle regular periodic updates
        pass

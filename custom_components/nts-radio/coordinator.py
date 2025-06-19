"""Data update coordinator for NTS Radio integration."""

import logging
from datetime import timedelta
from typing import Any, Dict

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import API_URL, DEFAULT_TIMEOUT, DOMAIN

_LOGGER = logging.getLogger(__name__)


class NTSRadioDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching NTS Radio data."""

    def __init__(
        self,
        hass: HomeAssistant,
        update_interval: timedelta,
    ) -> None:
        """Initialize the data update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from NTS Radio API."""
        try:
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
                            processed_data[f"channel_{channel_name}"] = {
                                "channel_name": channel_name,
                                "now": channel_data.get("now", {}),
                                "next": channel_data.get("next", {}),
                            }

                    return processed_data

        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error communicating with API: {err}")
        except Exception as err:
            raise UpdateFailed(f"Unexpected error: {err}")

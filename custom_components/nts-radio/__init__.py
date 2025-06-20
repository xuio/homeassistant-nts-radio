"""The NTS Radio integration."""

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import async_track_time_change

from .const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)
from .coordinator import NTSRadioDataUpdateCoordinator
from .live_tracks import NTSLiveTracksHandler

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up NTS Radio from a config entry."""
    update_interval = entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    email = entry.data.get(CONF_EMAIL)
    password = entry.data.get(CONF_PASSWORD)

    _LOGGER.info(
        "Setting up NTS Radio with update interval: %s seconds", update_interval
    )

    # Initialize coordinator first
    coordinator = NTSRadioDataUpdateCoordinator(
        hass,
        update_interval=timedelta(seconds=update_interval),
        live_tracks_handler=None,
        favourites_enabled=True,
    )

    # Initialize live tracks handler if credentials provided
    live_tracks_handler = None
    if email and password:
        live_tracks_handler = NTSLiveTracksHandler(
            hass,
            email,
            password,
            update_callback=coordinator._handle_track_update,
            favourites_callback=coordinator._handle_favourites_update,
        )
        if await live_tracks_handler.async_init():
            await live_tracks_handler.async_start()
            # Update coordinator with the handler
            coordinator.live_tracks_handler = live_tracks_handler
            _LOGGER.info("NTS Radio: Live tracks handler initialized successfully")
        else:
            _LOGGER.warning("NTS Radio: Failed to initialize live tracks handler")
            live_tracks_handler = None

    # Fetch initial data
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        raise ConfigEntryNotReady from err

    # Set up time-based updates at :00 and :30
    async def update_at_fixed_times(now):
        """Force update at :00 and :30 minutes."""
        _LOGGER.debug("Forcing update at %s", now)
        await coordinator.async_request_refresh()

    # Track time changes for :00 and :30 updates
    unsub_timer = async_track_time_change(
        hass, update_at_fixed_times, minute=[0, 30], second=0
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "live_tracks_handler": live_tracks_handler,
        "unsub_timer": unsub_timer,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        entry_data = hass.data[DOMAIN].pop(entry.entry_id)

        # Cancel timer
        if unsub_timer := entry_data.get("unsub_timer"):
            unsub_timer()

        # Stop live tracks handler if it exists
        if live_tracks_handler := entry_data.get("live_tracks_handler"):
            await live_tracks_handler.async_stop()

    return unload_ok

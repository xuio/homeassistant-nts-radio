"""Live tracks handler for NTS Radio integration using the async gRPC Firestore API (nts-python).

This implementation relies on the helper library that lives in the
`custom_components/nts_radio/nts-python` folder.  Since that folder name contains
an illegal dash ("-"), we add the folder itself to `sys.path` and import the
modules directly from there.

The public interface (`NTSLiveTracksHandler`) is kept identical to the previous
version so that the rest of the integration (coordinator, sensors, …) continues
working unchanged.
"""

from __future__ import annotations

import asyncio
import html
import logging
import os
import sys
from typing import Any, Callable, Dict, List, Optional, Awaitable
import importlib.util

from homeassistant.core import HomeAssistant  # type: ignore

_LOGGER = logging.getLogger(__name__)

# Keep the same constant so the coordinator does not need to be changed.
TRACK_LIMIT = 15

# -----------------------------------------------------------------------------
# Dynamically load the nts-python helper package
# -----------------------------------------------------------------------------

_NTS_PKG_PATH = os.path.join(os.path.dirname(__file__), "nts-python")
if _NTS_PKG_PATH not in sys.path:
    sys.path.insert(0, _NTS_PKG_PATH)

# The helper library expects to be imported as the package "nts_radio_async_api".
# Because the folder on disk is named "nts-python", we load it manually and
# register it under that package name so that its internal relative imports
# (e.g. "from .auth import …") continue to work.

_PKG_NAME = "nts_radio_async_api"
_PKG_INIT_FILE = os.path.join(_NTS_PKG_PATH, "__init__.py")

try:
    spec = importlib.util.spec_from_file_location(
        _PKG_NAME, _PKG_INIT_FILE, submodule_search_locations=[_NTS_PKG_PATH]
    )
    if spec and spec.loader:  # safety check
        module = importlib.util.module_from_spec(spec)
        sys.modules[_PKG_NAME] = module
        spec.loader.exec_module(module)

        # Pull wanted symbols
        from nts_radio_async_api import NTSClient, LiveTrackEvent  # type: ignore  # noqa: E402
    else:  # pragma: no cover
        raise ImportError("Could not create module spec for nts-python helper package")

except Exception as exc:  # pragma: no cover
    # We purposefully catch *all* exceptions here because the package may be
    # missing its heavy dependencies (grpc, google-cloud-firestore, …) or the
    # import machinery could not initialise the package. In those cases we still
    # want Home Assistant to start; real-time track updates will just be
    # unavailable.
    _LOGGER.error(
        "Failed to import nts-python async client – live track updates disabled: %s",
        exc,
    )

    class _FallbackClient:  # pylint: disable=too-few-public-methods
        async def authenticate(self, *_args, **_kwargs):
            raise RuntimeError("nts-python package not available")

    NTSClient = _FallbackClient  # type: ignore  # noqa: N816
    LiveTrackEvent = None  # type: ignore


# -----------------------------------------------------------------------------
# Public handler class used by the rest of the integration
# -----------------------------------------------------------------------------

class NTSLiveTracksHandler:
    """Handle real-time live track updates using the async Firestore gRPC API."""

    def __init__(
        self,
        hass: HomeAssistant,
        email: Optional[str],
        password: Optional[str],
        update_callback: Optional[Callable[[int, List[Dict[str, Any]]], Awaitable[None]]] = None,
        favourites_callback: Optional[Callable[[List[Dict[str, Any]]], Awaitable[None]]] = None,
        *,
        ignore_unknown_tracks: bool = True,
    ) -> None:
        self.hass = hass
        self.email = email
        self.password = password
        self._update_callback = update_callback
        self._favourites_callback = favourites_callback
        self._ignore_unknown = ignore_unknown_tracks

        self._client: Any = None  # NTSClient when import succeeds
        self._authenticated = False

        # Per-channel track ring-buffer (most-recent first)
        self._channel_tracks: Dict[int, List[Dict[str, Any]]] = {1: [], 2: []}

        # Tasks that run the Firestore streaming listeners
        self._listen_tasks: List[asyncio.Task] = []

        # favourites cache
        self._favourites: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public helpers expected by the coordinator / sensors
    # ------------------------------------------------------------------

    @property
    def is_authenticated(self) -> bool:
        return self._authenticated

    def get_tracks(self, channel: int) -> List[Dict[str, Any]]:
        """Return the cached track list for *channel* (most-recent first)."""
        return self._channel_tracks.get(channel, [])

    def get_current_track(self, channel: int) -> Optional[Dict[str, Any]]:
        tracks = self.get_tracks(channel)
        return tracks[0] if tracks else None

    # ------------------------------------------------------------------
    # Home Assistant lifecycle helpers
    # ------------------------------------------------------------------

    async def async_init(self) -> bool:
        """Authenticate against Firebase via the helper client."""
        if not self.email or not self.password:
            _LOGGER.debug("NTS Radio: No credentials provided – skipping authentication")
            return False

        self._client = NTSClient()
        try:
            await self._client.authenticate(self.email, self.password)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.error("NTS Radio: Authentication failed – %s", exc)
            return False

        self._authenticated = True
        return True

    async def async_start(self) -> None:
        """Start listening for live track updates on both channels."""
        if not self._authenticated or not self._client:
            return

        # Channels are labelled as strings "1" and "2" for the API.
        for ch in (1, 2):
            task = asyncio.create_task(self._listen_channel(ch))
            self._listen_tasks.append(task)

        # watch favourites (single task)
        task_fav = asyncio.create_task(self._listen_favourites())
        self._listen_tasks.append(task_fav)

    async def async_stop(self) -> None:
        """Cancel listener tasks and wait for them to finish."""
        for task in self._listen_tasks:
            task.cancel()
        for task in self._listen_tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._listen_tasks.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _listen_channel(self, channel: int) -> None:
        """Listen for track updates on the given *channel* (1 or 2)."""
        assert self._client  # for type-checker

        api_channel = str(channel)
        buffer: List[Dict[str, Any]] = self._channel_tracks[channel]

        try:
            async for event in self._client.listen_live_tracks(api_channel, initial_snapshot=False):
                track = self._event_to_dict(event)

                if not track:
                    continue

                # de-duplication: compare with most recent track
                if buffer and buffer[0]["start_time"] == track["start_time"]:
                    continue  # same track already at head of list

                buffer.insert(0, track)
                # limit buffer size
                del buffer[TRACK_LIMIT:]

                _LOGGER.debug("NTS Radio: got track on channel %s – %s - %s", channel, track.get("artists"), track.get("title"))

                # Notify coordinator
                if self._update_callback:
                    await self._update_callback(channel, buffer)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            _LOGGER.error("NTS Radio: Listener for channel %s stopped due to error: %s", channel, exc)

    # ------------------------------------------------------------------
    # Favourites listener
    # ------------------------------------------------------------------

    async def _listen_favourites(self) -> None:
        """Listen for favourites list changes and maintain local cache."""
        if not self._client:
            return

        try:
            async for favourites in self._client.watch_favourites_with_details(cache=True):
                self._favourites = favourites
                _LOGGER.debug("NTS Radio: Updated favourites list (%d items)", len(favourites))

                if self._favourites_callback:
                    await self._favourites_callback(favourites)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            _LOGGER.error("NTS Radio: Favourites listener stopped due to error: %s", exc)

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    def _event_to_dict(self, event: Any) -> Dict[str, Any]:  # Accept any event-like object
        """Convert a *LiveTrackEvent* named-tuple to dict; return empty if unknown and filtering enabled."""
        if event is None:
            return {}

        # Determine if track has content
        has_artist = bool(event.artist_names)
        has_title = bool(event.song_title)

        if self._ignore_unknown and not (has_artist or has_title):
            return {}  # Skip unknown track

        artists_str = ", ".join(event.artist_names)
        return {
            "artists": html.unescape(artists_str),
            "title": html.unescape(event.song_title),
            "start_time": event.start_time,
        }

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_favourites(self) -> List[Dict[str, Any]]:
        return self._favourites

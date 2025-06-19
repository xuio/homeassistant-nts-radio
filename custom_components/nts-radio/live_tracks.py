"""Live tracks handler for NTS Radio integration."""

import asyncio
import html
import json
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import FIREBASE_CONFIG

_LOGGER = logging.getLogger(__name__)

# Track record limit
TRACK_LIMIT = 15

# Firebase Auth REST API
FIREBASE_AUTH_URL = (
    "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
)
FIREBASE_REFRESH_URL = "https://securetoken.googleapis.com/v1/token"
FIRESTORE_URL = (
    "https://firestore.googleapis.com/v1/projects/{}/databases/(default)/documents"
)


class NTSLiveTracksHandler:
    """Handle live tracks from Firebase."""

    def __init__(
        self,
        hass: HomeAssistant,
        email: Optional[str],
        password: Optional[str],
        update_callback: Optional[Callable] = None,
    ) -> None:
        """Initialize the handler."""
        self.hass = hass
        self.email = email
        self.password = password
        self._authenticated = False
        self._auth_token = None
        self._refresh_token = None
        self._user_id = None
        self._channel_tracks: Dict[int, List[Dict[str, Any]]] = {1: [], 2: []}
        self._update_callback = update_callback
        self._update_task = None
        self._session: Optional[aiohttp.ClientSession] = None

    async def async_init(self) -> bool:
        """Initialize Firebase connection."""
        if not self.email or not self.password:
            _LOGGER.debug("No credentials provided, skipping Firebase init")
            return False

        try:
            self._session = aiohttp.ClientSession()

            # Authenticate with Firebase
            auth_data = {
                "email": self.email,
                "password": self.password,
                "returnSecureToken": True,
            }

            async with self._session.post(
                f"{FIREBASE_AUTH_URL}?key={FIREBASE_CONFIG['apiKey']}", json=auth_data
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self._auth_token = data.get("idToken")
                    self._refresh_token = data.get("refreshToken")
                    self._user_id = data.get("localId")
                    self._authenticated = True
                    _LOGGER.info("Successfully authenticated with NTS/Firebase")
                    _LOGGER.debug("User ID: %s", self._user_id)
                    return True
                else:
                    error_data = await response.json()
                    error_msg = error_data.get("error", {}).get(
                        "message", "Unknown error"
                    )

                    if error_msg == "INVALID_EMAIL":
                        _LOGGER.error("Invalid email address format")
                    elif error_msg == "EMAIL_NOT_FOUND":
                        _LOGGER.error(
                            "Email not found. Please check your NTS account email"
                        )
                    elif error_msg == "INVALID_PASSWORD":
                        _LOGGER.error(
                            "Invalid password. Please check your NTS account password"
                        )
                    elif error_msg == "USER_DISABLED":
                        _LOGGER.error("This NTS account has been disabled")
                    else:
                        _LOGGER.error("Authentication failed: %s", error_msg)

                    return False

        except aiohttp.ClientError as err:
            _LOGGER.error("Network error during authentication: %s", err)
            return False
        except Exception as err:
            _LOGGER.error("Failed to initialize Firebase: %s", err)
            return False

    async def async_start(self) -> None:
        """Start listening for track updates."""
        if not self._authenticated:
            return

        # Start update loop
        self._update_task = asyncio.create_task(self._update_loop())

    async def async_stop(self) -> None:
        """Stop listening for track updates."""
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass

        if self._session:
            await self._session.close()

    async def _refresh_auth_token(self) -> bool:
        """Refresh the authentication token."""
        if not self._refresh_token:
            return False

        try:
            refresh_data = {
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token,
            }

            async with self._session.post(
                f"{FIREBASE_REFRESH_URL}?key={FIREBASE_CONFIG['apiKey']}",
                json=refresh_data,
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self._auth_token = data.get("id_token")
                    self._refresh_token = data.get("refresh_token", self._refresh_token)
                    return True
                else:
                    _LOGGER.error("Failed to refresh token")
                    return False

        except Exception as err:
            _LOGGER.error("Error refreshing token: %s", err)
            return False

    async def _update_loop(self) -> None:
        """Periodically fetch track updates."""
        while True:
            try:
                # Fetch tracks for both channels
                for channel in [1, 2]:
                    await self._fetch_channel_tracks(channel)

                # Wait before next update
                await asyncio.sleep(30)  # Update every 30 seconds

            except asyncio.CancelledError:
                raise
            except Exception as err:
                _LOGGER.error("Error in update loop: %s", err)
                # Try to refresh token
                if await self._refresh_auth_token():
                    _LOGGER.info("Successfully refreshed auth token")
                await asyncio.sleep(60)  # Wait longer on error

    async def _fetch_channel_tracks(self, channel: int) -> None:
        """Fetch tracks for a channel."""
        if not self._auth_token:
            return

        try:
            # Use the same pathname format as the desktop app
            stream_pathname = "/stream" if channel == 1 else "/stream2"

            # Query Firestore using REST API
            url = f"{FIRESTORE_URL.format(FIREBASE_CONFIG['projectId'])}/live_tracks"

            # Build structured query
            query = {
                "structuredQuery": {
                    "from": [{"collectionId": "live_tracks"}],
                    "where": {
                        "fieldFilter": {
                            "field": {"fieldPath": "stream_pathname"},
                            "op": "EQUAL",
                            "value": {"stringValue": stream_pathname},
                        }
                    },
                    "orderBy": [
                        {
                            "field": {"fieldPath": "start_time"},
                            "direction": "DESCENDING",
                        }
                    ],
                    "limit": TRACK_LIMIT,
                }
            }

            headers = {
                "Authorization": f"Bearer {self._auth_token}",
                "Content-Type": "application/json",
            }

            # Use the runQuery endpoint for complex queries
            query_url = f"{FIRESTORE_URL.format(FIREBASE_CONFIG['projectId'])}:runQuery"

            _LOGGER.debug("Fetching tracks for channel %s from: %s", channel, query_url)
            _LOGGER.debug("Query: %s", json.dumps(query, indent=2))

            async with self._session.post(
                query_url, json=query, headers=headers
            ) as response:
                if response.status == 200:
                    response_data = await response.json()
                    _LOGGER.debug(
                        "Got %d documents for channel %s", len(response_data), channel
                    )

                    # Process documents and filter out empty tracks
                    tracks = []

                    for doc_wrapper in response_data:
                        if "document" not in doc_wrapper:
                            continue

                        doc = doc_wrapper["document"]
                        fields = doc.get("fields", {})

                        # Extract artist names
                        artists = []
                        artist_names = fields.get("artist_names", {})
                        if (
                            "arrayValue" in artist_names
                            and "values" in artist_names["arrayValue"]
                        ):
                            for artist in artist_names["arrayValue"]["values"]:
                                if "stringValue" in artist and artist["stringValue"]:
                                    # Decode HTML entities in artist names
                                    artist_name = html.unescape(artist["stringValue"])
                                    artists.append(artist_name)

                        # Extract song title
                        song_title = ""
                        if (
                            "song_title" in fields
                            and "stringValue" in fields["song_title"]
                        ):
                            # Decode HTML entities in song title
                            song_title = html.unescape(fields["song_title"]["stringValue"])

                        # Only add tracks that have either artists or title (not empty)
                        if artists or song_title:
                            # Extract timestamp
                            start_time = None
                            if (
                                "start_time" in fields
                                and "timestampValue" in fields["start_time"]
                            ):
                                start_time = fields["start_time"]["timestampValue"]

                            # Format artists as a comma-separated string
                            artists_str = ", ".join(artists) if artists else ""

                            track = {
                                "artists": artists_str,
                                "title": song_title,
                                "start_time": start_time,
                            }
                            tracks.append(track)
                            _LOGGER.debug(
                                "Found track with content: %s - %s",
                                artists_str if artists_str else "Unknown",
                                song_title,
                            )
                        else:
                            _LOGGER.debug("Skipped empty track")

                    # Update channel data with filtered tracks
                    self._channel_tracks[channel] = tracks
                    _LOGGER.info(
                        "Updated channel %s with %s tracks (filtered from %s)",
                        channel,
                        len(tracks),
                        len(response_data),
                    )

                    # Log the latest track with content
                    if tracks:
                        latest = tracks[0]
                        _LOGGER.info(
                            "Latest track on channel %s: %s - %s",
                            channel,
                            latest["artists"],
                            latest["title"],
                        )
                    else:
                        _LOGGER.info(
                            "No tracks with content found for channel %s", channel
                        )

                    # Notify coordinator with callback
                    if self._update_callback:
                        await self._update_callback(channel, tracks)

                elif response.status == 401:
                    # Token expired, try to refresh
                    _LOGGER.warning("Token expired, attempting refresh")
                    if await self._refresh_auth_token():
                        # Retry the request
                        await self._fetch_channel_tracks(channel)
                elif response.status == 403:
                    error_text = await response.text()
                    _LOGGER.error(
                        "Access denied to track data. Response: %s", error_text
                    )
                else:
                    error_text = await response.text()
                    _LOGGER.error(
                        "Error fetching tracks for channel %s: %s - %s",
                        channel,
                        response.status,
                        error_text,
                    )

        except Exception as err:
            _LOGGER.error("Error fetching tracks for channel %s: %s", channel, err)

    def get_tracks(self, channel: int) -> List[Dict[str, Any]]:
        """Get current tracks for a channel (filtered to only show tracks with content)."""
        return self._channel_tracks.get(channel, [])

    def get_current_track(self, channel: int) -> Optional[Dict[str, Any]]:
        """Get the most recent track with content for a channel."""
        tracks = self._channel_tracks.get(channel, [])
        return tracks[0] if tracks else None

    @property
    def is_authenticated(self) -> bool:
        """Return if handler is authenticated."""
        return self._authenticated

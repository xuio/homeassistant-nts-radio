# NTS Radio Integration for Home Assistant

This custom integration allows you to track what's currently playing on NTS Radio's two channels in Home Assistant.

## Features

- Creates devices for each NTS channel with multiple sensors
- Shows the currently playing show name or track info (if authenticated)
- Displays show artwork as entity picture
- Provides detailed attributes including:
  - Show description
  - Location
  - Genres
  - Start/end times
  - Whether it's a replay
  - Next show information
- **Track Information (with authentication)**
  - Current track artist and title
  - Recent tracks history (last 10 tracks)
  - Real-time track updates
- **Smart Polling**: Automatically updates at :00 and :30 to catch new shows immediately
- Configurable update interval (30-300 seconds)

## Installation

### Manual Installation

1. Copy the `nts-radio` folder to your `config/custom_components/` directory
2. Restart Home Assistant
3. Go to Configuration > Integrations
4. Click the "+" button and search for "NTS Radio"
5. Follow the configuration steps

### HACS Installation (Future)

This integration is not yet available in HACS but may be added in the future.

## Configuration

During setup, you can configure:
- **Update Interval**: How often to check for new shows (default: 60 seconds, range: 30-300 seconds)
  - The integration uses smart polling to always update at :00 and :30 minutes regardless of this setting
  - This ensures new shows are detected immediately when they start
  - Between these fixed times, it will update based on your configured interval
- **Email** (optional): Your NTS account email for accessing track information
- **Password** (optional): Your NTS account password for accessing track information

### Authentication (Optional - NTS Supporters Only)

Track identification features are available for NTS Supporters. To enable:

1. Ensure you have an active [NTS Supporter](https://www.nts.live/supporters) account
2. Enter your NTS account email and password during setup
3. The integration will authenticate with Firebase to access track data

**Note**: Track features are only available to NTS Supporters. Regular NTS accounts will not have access to track identification.

## Devices and Entities

The integration creates two devices, one for each NTS channel:

### Device: NTS Channel 1
- `sensor.nts_channel_1` - Main sensor showing what's currently playing
- `sensor.nts_channel_1_next_show` - Next scheduled show (with picture)
- `sensor.nts_channel_1_track_id` - Track ID (shows track or show info)

### Device: NTS Channel 2
- `sensor.nts_channel_2` - Main sensor showing what's currently playing
- `sensor.nts_channel_2_next_show` - Next scheduled show (with picture)
- `sensor.nts_channel_2_track_id` - Track ID (shows track or show info)

### Sensor Details

#### Main Sensor (Now Playing)
Shows the current show name or "Artist - Track" if authenticated.

**Attributes:**
- `show_name`: Full name of the current show
- `description`: Show description
- `location`: Broadcasting location
- `genres`: Music genres (comma-separated)
- `start_time`: Show start time (ISO format)
- `end_time`: Show end time (ISO format)
- `image_url`: URL to show artwork
- `is_replay`: Boolean indicating if it's a replay
- `authenticated`: Boolean indicating if track data is available
- `recent_tracks`: List of recently played tracks (if authenticated)

#### Next Show Sensor
Shows the name of the next scheduled show with its artwork as entity picture.

**Attributes:**
- `start_time`: When the next show starts
- `end_time`: When the next show ends
- `is_replay`: Boolean indicating if it's a replay
- `image_url`: URL to the next show's artwork

#### Track ID Sensor
Shows the current track ID as "Artist - Title" when available, or the show name when track info is not available.

**Attributes when showing track:**
- `artist`: The track artist(s)
- `title`: The track title
- `start_time`: When the track started playing
- `track_number`: Position in recent tracks (always 1 for current)
- `total_recent_tracks`: Total number of recent tracks available

**Attributes when showing show:**
- `info_type`: Set to "show" when displaying show info
- `show_name`: The current show name

### Track ID Support
The integration supports fetching track IDs when NTS Radio is playing music tracks. This feature requires:
1. An NTS Supporter account with valid credentials
2. Some shows may have segments without track information (talk segments, jingles, etc.)

**Important**: The Track ID sensor only displays tracks that have actual artist or title information. Empty tracks are automatically filtered out. If no tracks with content are available, the sensor will show the current show name instead.

When tracks are available, the sensor shows:

## Example Automations

### New Track Notification
```yaml
automation:
  - alias: "NTS New Track Notification"
    trigger:
      - platform: state
        entity_id: sensor.nts_channel_1_track_id
    condition:
      - condition: template
        value_template: "{{ trigger.from_state.state != trigger.to_state.state }}"
      - condition: template
        value_template: "{{ state_attr('sensor.nts_channel_1_track_id', 'artist') != None }}"
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "New track on NTS Channel 1"
          message: "Now playing: {{ states('sensor.nts_channel_1_track_id') }}"
```

### New Show Starting
```yaml
automation:
  - alias: "NTS New Show Alert"
    trigger:
      - platform: state
        entity_id: sensor.nts_channel_1
        attribute: show_name
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "New show on NTS Channel 1"
          message: "Starting now: {{ state_attr('sensor.nts_channel_1', 'show_name') }}"
```

## Dashboard Card Examples

### Device Card
```yaml
type: device
device_id: YOUR_DEVICE_ID_HERE
```

### Custom Cards

#### Channel Overview
```yaml
type: vertical-stack
cards:
  - type: markdown
    content: |
      ## NTS Channel 1
      **Now:** {{ states('sensor.nts_channel_1') }}
      **Next:** {{ states('sensor.nts_channel_1_next_show') }}
      {% if state_attr('sensor.nts_channel_1_track_id', 'artist') %}
      **Track:** {{ state_attr('sensor.nts_channel_1_track_id', 'title') }}
      **Artist:** {{ state_attr('sensor.nts_channel_1_track_id', 'artist') }}
      {% else %}
      **Playing:** {{ states('sensor.nts_channel_1_track_id') }}
      {% endif %}

  - type: entities
    entities:
      - sensor.nts_channel_1
      - sensor.nts_channel_1_next_show
      - sensor.nts_channel_1_track_id
```

#### Picture Elements Card
```yaml
type: picture-elements
image: "{{ state_attr('sensor.nts_channel_1', 'image_url') }}"
elements:
  - type: state-label
    entity: sensor.nts_channel_1
    style:
      bottom: 0
      left: 0
      right: 0
      background-color: "rgba(0, 0, 0, 0.7)"
      color: white
      padding: 10px
```

#### Next Show Card with Picture
```yaml
type: picture-entity
entity: sensor.nts_channel_1_next_show
show_state: true
show_name: true
```

## Known Limitations

- The integration relies on the public NTS API which may have rate limits
- Show artwork may not always be available
- Track information requires an active NTS Supporter account
- Firebase connection may occasionally need to reconnect

## Troubleshooting

### Track information not showing
1. Ensure you have an active NTS Supporter account
2. Verify your email and password are correct
3. Check the Home Assistant logs for authentication errors
4. Restart Home Assistant after adding credentials
5. Enable debug logging (see below)

### Authentication errors in logs
Common error messages:
- **"Invalid email/password"**: Double-check your NTS account credentials
- **"Email not found"**: Make sure you're using the email associated with your NTS account
- **"Access denied"**: Ensure your NTS Supporter subscription is active

### Enable Debug Logging
To troubleshoot issues, enable debug logging for the integration:

```yaml
logger:
  default: info
  logs:
    custom_components.nts_radio: debug
```

After enabling debug logging, restart Home Assistant and check the logs for detailed information about:
- Authentication success/failure
- Track fetching from Firebase
- API responses
- Update timing

The integration will continue to work normally for show information even without authentication.

## Support

For issues or feature requests, please create an issue in the repository.

## License

This integration is provided as-is under the MIT license.
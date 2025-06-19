# NTS Radio Integration for Home Assistant

This custom integration allows you to track what's currently playing on NTS Radio's two channels in Home Assistant.

## Features

- Creates two sensors - one for each NTS channel
- Shows the currently playing show name
- Displays show artwork as entity picture
- Provides detailed attributes including:
  - Show description
  - Location
  - Genres
  - Start/end times
  - Whether it's a replay
  - Next show information
- Configurable update interval (30-300 seconds)

## Installation

### HACS Installation

Install this Integration via HACS by adding this repo as a custom repository.

### Manual Installation

1. Copy the `nts-radio` folder to your `config/custom_components/` directory
2. Restart Home Assistant
3. Go to Configuration > Integrations
4. Click the "+" button and search for "NTS Radio"
5. Follow the configuration steps

## Configuration

During setup, you can configure:
- **Update Interval**: How often to check for new shows (default: 60 seconds, range: 30-300 seconds)

## Entities

The integration creates two sensor entities:

- `sensor.nts_channel_1` - Shows what's playing on NTS Channel 1
- `sensor.nts_channel_2` - Shows what's playing on NTS Channel 2

### Attributes

Each sensor provides the following attributes:

- `show_name`: Full name of the current show
- `description`: Show description
- `location`: Broadcasting location
- `genres`: Music genres (comma-separated)
- `start_time`: Show start time (ISO format)
- `end_time`: Show end time (ISO format)
- `image_url`: URL to show artwork
- `is_replay`: Boolean indicating if it's a replay
- `next_show`: Name of the next show
- `next_start_time`: Start time of the next show

## Example Automation

Here's an example automation that sends a notification when a new show starts:

```yaml
automation:
  - alias: "NTS New Show Notification"
    trigger:
      - platform: state
        entity_id: sensor.nts_channel_1
    condition:
      - condition: template
        value_template: "{{ trigger.from_state.state != trigger.to_state.state }}"
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "New show on NTS Channel 1"
          message: "Now playing: {{ states('sensor.nts_channel_1') }}"
```

## Dashboard Card Example

Here's a simple card configuration to display NTS Radio information:

```yaml
type: entities
title: NTS Radio
entities:
  - entity: sensor.nts_channel_1
    name: Channel 1
  - entity: sensor.nts_channel_2
    name: Channel 2
```

## Known Limitations

- The integration relies on the public NTS API which may have rate limits
- Show artwork may not always be available
- API may not always provide complete information for all shows

## Support

For issues or feature requests, please create an issue in the repository.

## License

This integration is provided as-is under the MIT license.

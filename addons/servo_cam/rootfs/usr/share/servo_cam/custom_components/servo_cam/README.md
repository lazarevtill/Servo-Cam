# Servo Security Camera - Home Assistant Integration

A comprehensive Home Assistant integration for the Servo Security Camera system with pan/tilt control, intelligent motion detection, scene change monitoring, and autonomous patrol capabilities.

## Features

- **Full Camera Integration**
  - Live MJPEG video streaming
  - Snapshot capture
  - Motion detection with binary sensor
  - Camera control (on/off = monitoring start/stop)

- **Pan/Tilt Servo Control**
  - Real-time pan/tilt angle sensors (0-180°)
  - Manual position control via services
  - 9 preset positions (center, left, right, up, down, corners)
  - Smooth servo movement

- **Intelligent Motion Detection**
  - Multi-dimensional motion analysis
  - Classification (person, vehicle, animal, environmental)
  - Threat level assessment (0.0-1.0)
  - Confidence scoring with adaptive validation
  - Motion persistence tracking
  - False alert reduction (80-85%)

- **Scene Change Detection**
  - Brightness-normalized comparison (structural changes only)
  - Per-position baseline storage
  - Adaptive baseline blending
  - Independent of lighting changes (sunrise/sunset, clouds)

- **Autonomous Patrol Mode**
  - Configurable pan/tilt grid scanning
  - Default: 15 positions (5 pan × 3 tilt)
  - Adjustable dwell time per position
  - Scene monitoring at each patrol position

- **Home Assistant Entities**
  - **Camera**: Live stream with snapshot support
  - **Sensors**: Pan/tilt angles, motion count, alert count, session duration, frame count, threat levels
  - **Binary Sensors**: Monitoring state, patrol state, servo/camera status, motion detected
  - **Switches**: Monitoring control, patrol mode toggle
  - **Services**: Manual servo control, preset positions, patrol control

## Installation

### Method 1: Home Assistant Add-on (Recommended)

1. Settings → Add-ons → Add-on Store → ⋮ → Repositories
2. Add `https://github.com/lazarevtill/Servo-Cam`
3. Install and start the **Servo Cam** add-on (enable auto-start/watchdog as desired)
4. The add-on copies this integration into `/config/custom_components/servo_cam` automatically on every boot

### Method 2: HACS

1. Ensure [HACS](https://hacs.xyz/) is installed
2. Add this repository as a custom repository in HACS:
   - Open HACS
   - Click "Integrations"
   - Click the three dots menu (top right)
   - Select "Custom repositories"
   - Add repository URL: `https://github.com/lazarevtill/Servo-Cam`
   - Category: Integration
3. Click "Install"
4. Restart Home Assistant

### Method 3: Manual Installation

1. Copy the `custom_components/servo_cam` directory to your Home Assistant `custom_components` folder:
   ```bash
   cd /path/to/homeassistant
   mkdir -p custom_components
   cp -r /path/to/servo-cam/custom_components/servo_cam custom_components/
   ```

2. Restart Home Assistant

> 💡 Tip: Running `./install.sh --systemd --start` from the project root on your Raspberry Pi performs this copy automatically, provisions dependencies, and keeps the backend running. Use `HA_CONFIG_DIR=/path/to/config ./install.sh --systemd --start` to target a different Home Assistant configuration directory.

## Configuration

### Setup via UI (Recommended)

1. Go to **Settings** → **Devices & Services**
2. If the Zeroconf discovery prompt appears, click **Configure**. Otherwise click **+ Add Integration** and search for "Servo Security Camera".
3. Enter or confirm connection details:
   - **Host**: IP address or hostname of your Raspberry Pi (default: `servo-cam.local`; change to your Pi's IP if needed)
   - **Port**: API port (default: `5000`)
4. Click **Submit**

The integration will automatically discover and configure all entities.

### Manual Configuration (YAML)

Not supported - use UI configuration only.

## Entities

### Camera

- `camera.servo_security_camera` - Live MJPEG stream with snapshot support
  - Attributes: `pan_angle`, `tilt_angle`, `servo_connected`, `frame_count`, `motion_count`, `webhook_count`, `session_duration`

### Sensors

- `sensor.servo_cam_pan_angle` - Current pan angle (0-180°)
- `sensor.servo_cam_tilt_angle` - Current tilt angle (0-180°)
- `sensor.servo_cam_motion_detections` - Total motion detections
- `sensor.servo_cam_alerts_sent` - Total alerts/webhooks sent
- `sensor.servo_cam_session_duration` - Monitoring session duration (seconds)
- `sensor.servo_cam_frames_processed` - Total frames processed
- `sensor.servo_cam_last_motion_classification` - Classification of last detected motion
- `sensor.servo_cam_last_motion_threat_level` - Threat level of last motion (0.0-1.0)
- `sensor.servo_cam_alert_queue_size` - Current webhook queue size

### Binary Sensors

- `binary_sensor.servo_cam_monitoring_active` - Monitoring state
- `binary_sensor.servo_cam_patrol_active` - Patrol mode state
- `binary_sensor.servo_cam_servo_connected` - Servo connectivity
- `binary_sensor.servo_cam_camera_active` - Camera status
- `binary_sensor.servo_cam_motion_detected` - Motion detection state

### Switches

- `switch.servo_cam_monitoring` - Control monitoring mode
- `switch.servo_cam_patrol_mode` - Control patrol mode (requires monitoring active)

## Services

### `servo_cam.move_servo`

Move camera to specific pan and tilt angles.

```yaml
service: servo_cam.move_servo
data:
  pan: 90  # 0-180°
  tilt: 165  # 0-180°
```

### `servo_cam.preset_position`

Move camera to a predefined preset position.

```yaml
service: servo_cam.preset_position
data:
  position: center  # center, left, right, up, down, top_left, top_right, bottom_left, bottom_right
```

Available presets:
- `center`: 90°, 165°
- `left`: 30°, 165°
- `right`: 150°, 165°
- `up`: 90°, 150°
- `down`: 90°, 180°
- `top_left`: 30°, 150°
- `top_right`: 150°, 150°
- `bottom_left`: 30°, 180°
- `bottom_right`: 150°, 180°

### `servo_cam.start_patrol`

Start autonomous patrol mode (requires monitoring active).

```yaml
service: servo_cam.start_patrol
```

### `servo_cam.stop_patrol`

Stop autonomous patrol mode.

```yaml
service: servo_cam.stop_patrol
```

### `servo_cam.center_camera`

Move camera to center position (shortcut for preset center).

```yaml
service: servo_cam.center_camera
```

## Automation Examples

### Alert on High-Threat Motion Detection

```yaml
automation:
  - alias: "Security Camera - High Threat Alert"
    trigger:
      - platform: numeric_state
        entity_id: sensor.servo_cam_last_motion_threat_level
        above: 0.7
    condition:
      - condition: state
        entity_id: binary_sensor.servo_cam_motion_detected
        state: "on"
    action:
      - service: notify.mobile_app
        data:
          title: "Security Alert: High Threat Detected"
          message: "Motion classified as {{ state_attr('sensor.servo_cam_last_motion_classification', 'classification') }}"
          data:
            entity_id: camera.servo_security_camera
            image: /api/camera_proxy/camera.servo_security_camera
```

### Start Monitoring at Sunset

```yaml
automation:
  - alias: "Security Camera - Start at Sunset"
    trigger:
      - platform: sun
        event: sunset
        offset: "-00:30:00"
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.servo_cam_monitoring
```

### Stop Monitoring at Sunrise

```yaml
automation:
  - alias: "Security Camera - Stop at Sunrise"
    trigger:
      - platform: sun
        event: sunrise
        offset: "00:30:00"
    action:
      - service: switch.turn_off
        target:
          entity_id: switch.servo_cam_monitoring
```

### Patrol Mode During Night

```yaml
automation:
  - alias: "Security Camera - Night Patrol"
    trigger:
      - platform: time
        at: "22:00:00"
    condition:
      - condition: state
        entity_id: binary_sensor.servo_cam_monitoring_active
        state: "on"
    action:
      - service: servo_cam.start_patrol
```

### Move to Specific Position on Motion

```yaml
automation:
  - alias: "Security Camera - Focus on Entrance"
    trigger:
      - platform: state
        entity_id: binary_sensor.front_door
        to: "on"
    action:
      - service: servo_cam.move_servo
        data:
          pan: 120
          tilt: 165
```

### Alert on Person Detection

```yaml
automation:
  - alias: "Security Camera - Person Detected"
    trigger:
      - platform: state
        entity_id: binary_sensor.servo_cam_motion_detected
        to: "on"
    condition:
      - condition: template
        value_template: "{{ state_attr('sensor.servo_cam_last_motion_classification', 'classification') == 'person' }}"
    action:
      - service: notify.telegram
        data:
          title: "Person Detected"
          message: "Threat level: {{ states('sensor.servo_cam_last_motion_threat_level') }}"
```

## Lovelace Dashboard Card

### Camera Card with Controls

```yaml
type: vertical-stack
cards:
  - type: picture-entity
    entity: camera.servo_security_camera
    camera_view: live
    show_state: false
    show_name: false

  - type: horizontal-stack
    cards:
      - type: button
        entity: switch.servo_cam_monitoring
        icon: mdi:eye
        show_name: true
        show_state: true

      - type: button
        entity: switch.servo_cam_patrol_mode
        icon: mdi:routes
        show_name: true
        show_state: true

  - type: entities
    title: Camera Status
    entities:
      - entity: sensor.servo_cam_pan_angle
      - entity: sensor.servo_cam_tilt_angle
      - entity: binary_sensor.servo_cam_motion_detected
      - entity: sensor.servo_cam_last_motion_classification
      - entity: sensor.servo_cam_last_motion_threat_level
      - entity: sensor.servo_cam_motion_detections
      - entity: sensor.servo_cam_alerts_sent

  - type: grid
    title: Preset Positions
    columns: 3
    square: true
    cards:
      - type: button
        icon: mdi:arrow-top-left
        tap_action:
          action: call-service
          service: servo_cam.preset_position
          data:
            position: top_left

      - type: button
        icon: mdi:arrow-up
        tap_action:
          action: call-service
          service: servo_cam.preset_position
          data:
            position: up

      - type: button
        icon: mdi:arrow-top-right
        tap_action:
          action: call-service
          service: servo_cam.preset_position
          data:
            position: top_right

      - type: button
        icon: mdi:arrow-left
        tap_action:
          action: call-service
          service: servo_cam.preset_position
          data:
            position: left

      - type: button
        icon: mdi:circle-medium
        tap_action:
          action: call-service
          service: servo_cam.center_camera

      - type: button
        icon: mdi:arrow-right
        tap_action:
          action: call-service
          service: servo_cam.preset_position
          data:
            position: right

      - type: button
        icon: mdi:arrow-bottom-left
        tap_action:
          action: call-service
          service: servo_cam.preset_position
          data:
            position: bottom_left

      - type: button
        icon: mdi:arrow-down
        tap_action:
          action: call-service
          service: servo_cam.preset_position
          data:
            position: down

      - type: button
        icon: mdi:arrow-bottom-right
        tap_action:
          action: call-service
          service: servo_cam.preset_position
          data:
            position: bottom_right
```

### Compact Status Card

```yaml
type: entities
title: Security Camera
show_header_toggle: false
entities:
  - entity: camera.servo_security_camera
  - entity: switch.servo_cam_monitoring
  - entity: switch.servo_cam_patrol_mode
  - type: divider
  - entity: binary_sensor.servo_cam_motion_detected
  - entity: sensor.servo_cam_last_motion_classification
  - entity: sensor.servo_cam_last_motion_threat_level
  - type: divider
  - entity: sensor.servo_cam_pan_angle
  - entity: sensor.servo_cam_tilt_angle
```

## Performance Optimization

The integration is optimized for Raspberry Pi performance:

- **Async operations**: All API calls use `aiohttp` for non-blocking I/O
- **Connection pooling**: Single session reused across requests
- **Update throttling**: 1-second update interval (configurable)
- **Efficient streaming**: Direct MJPEG passthrough without re-encoding
- **Minimal polling**: Relies on coordinator updates instead of entity polling

## Troubleshooting

### Integration Not Found

- Ensure you've copied files to the correct directory
- Restart Home Assistant after installation
- Check logs: Settings → System → Logs

### Cannot Connect Error

- Verify the Servo Camera system is running
- Check host/port configuration
- Test connectivity: `curl http://<host>:<port>/healthz`
- Ensure firewall allows port 5000

### Streaming Not Working

- Verify monitoring is active (`switch.servo_cam_monitoring` = on)
- Check camera feed directly: `http://<host>:<port>/video_feed`
- Review Home Assistant logs for errors

### Services Not Appearing

- Confirm integration loaded successfully
- Restart Home Assistant
- Check Services tab in Developer Tools

## Advanced Configuration

### Adjust Update Interval

Edit `const.py` and modify:
```python
UPDATE_INTERVAL = 1  # seconds
```

### Add Custom Preset Positions

Edit `const.py` and add to `PRESET_POSITIONS`:
```python
PRESET_POSITIONS = {
    # ... existing presets ...
    "custom_view": {"pan": 45.0, "tilt": 160.0},
}
```

Then add to `services.yaml` options list.

## System Requirements

- Home Assistant Core 2023.1 or newer
- Servo Camera system running on Raspberry Pi
- Network connectivity between HA and camera system

## Support

- **Issues**: https://github.com/lazarevtill/servo-cam/issues
- **Documentation**: https://github.com/lazarevtill/servo-cam

## License

MIT License - see main repository for details

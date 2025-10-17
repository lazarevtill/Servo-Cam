# Home Assistant Integration Guide

Complete guide for integrating the Servo Security Camera system with Home Assistant.

## Overview

This integration provides full control and monitoring of your Servo Security Camera through Home Assistant, including:

- Live camera streaming (MJPEG)
- Pan/tilt servo control with presets
- Intelligent motion detection with classification
- Scene change monitoring
- Autonomous patrol mode
- Comprehensive sensors and automation support

## Quick Start

### 1. Install the Integration

#### Option A: Home Assistant Add-on (Recommended)

1. Go to **Settings → Add-ons → Add-on Store**.
2. Open the **⋮** menu → **Repositories** and add `https://github.com/lazarevtill/Servo-Cam`.
3. Select **Servo Cam** → **Install** → **Start** (enable auto-start/watchdog if desired).

The add-on automatically copies the integration into `/config/custom_components/servo_cam` on every boot and keeps the backend service running.

#### Option B: Manual Filesystem Installation

```bash
# From the servo-cam directory
cp -r custom_components/servo_cam /path/to/homeassistant/custom_components/
```

#### Option C: Symlink (Development)

```bash
# From Home Assistant config directory
cd custom_components
ln -s /root/servo-cam-main/custom_components/servo_cam servo_cam
```

### 2. Restart Home Assistant or Start the Add-on

```bash
# Docker
docker restart homeassistant

# Supervised/OS
ha core restart

# Core
systemctl restart home-assistant@homeassistant
```

### 3. Add Integration via UI

1. Keep `python3 main.py` running so the Zeroconf advertisement stays online.
2. Navigate to **Settings** → **Devices & Services** in Home Assistant.
3. A **"New device discovered"** prompt for **Servo Security Camera** should appear automatically. Click **Configure**.
4. If you dismiss the prompt, click **+ Add Integration** and search for "Servo Security Camera".
5. Confirm the detected connection details:
   - **Host**: `192.168.1.xxx` (your Raspberry Pi IP)
   - **Port**: `5000` (default)
6. Click **Submit**

### 4. Verify Setup

All entities should appear automatically:
- 1 Camera entity
- 9 Sensor entities
- 5 Binary sensor entities
- 2 Switch entities
- 5 Service calls available

## Architecture

### Communication Flow

```
Home Assistant
    ↓ (HTTP/REST API)
Coordinator (aiohttp)
    ↓
Servo Camera Flask API (port 5000)
    ↓
MonitoringService (DDD application layer)
    ↓
Infrastructure (Camera, Servo, Motion Detection)
```

### Update Mechanism

- **Coordinator**: Polls `/status` endpoint every 1 second
- **Camera**: Direct MJPEG stream passthrough (no polling)
- **Snapshot**: On-demand via `/snapshot` endpoint
- **Commands**: Direct POST to Flask API endpoints

## API Endpoints Used

The integration communicates with these endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/healthz` | GET | Health check during setup |
| `/status` | GET | System status (coordinator polling) |
| `/snapshot` | GET | Camera snapshot (on-demand) |
| `/video_feed` | GET | MJPEG stream |
| `/monitoring/start` | POST | Start monitoring |
| `/monitoring/stop` | POST | Stop monitoring |
| `/servo/move` | POST | Move servo to position |
| `/config` | GET/POST | Get/update configuration |

## Entity Details

### Camera Entity

**Entity ID**: `camera.servo_security_camera`

**Capabilities**:
- Live MJPEG streaming via `stream_source()`
- Snapshot capture via `async_camera_image()`
- On/Off control (starts/stops monitoring)
- Motion detection support

**Attributes**:
```yaml
pan_angle: 90.0
tilt_angle: 165.0
servo_connected: true
frame_count: 12345
motion_count: 42
webhook_count: 8
session_duration: 3600
```

### Sensors

#### Pan/Tilt Sensors
- Real-time angle updates
- Unit: degrees (°)
- Range: 0-180°
- Update frequency: 1s

#### Statistics Sensors
- Motion detections (total count)
- Alerts sent (webhook count)
- Session duration (seconds)
- Frames processed (total count)
- Alert queue size (current)

#### Intelligence Sensors
- Last motion classification (person/vehicle/animal/environmental/unknown)
- Last motion threat level (0.0-1.0, higher = more threatening)
- Includes confidence, speed, and timestamp attributes

### Binary Sensors

#### States
- `monitoring_active`: System is actively monitoring
- `patrol_active`: Autonomous patrol is running
- `servo_connected`: Servo hardware is connected
- `camera_active`: Camera is capturing frames
- `motion_detected`: Motion currently detected

#### Attributes on Motion Detected
```yaml
classification: person
threat_level: 0.75
confidence: 0.85
timestamp: 2025-10-17T12:34:56
```

### Switches

#### Monitoring Switch
- Controls monitoring session
- When ON: Camera actively processes frames, detects motion, sends webhooks
- When OFF: Camera stops, servos idle

#### Patrol Switch
- Controls autonomous patrol mode
- **Requires monitoring to be ON**
- When ON: Camera scans through predefined grid of positions
- When OFF: Camera stays in current position

## Services

### Movement Services

#### `servo_cam.move_servo`
Manual position control with degree precision.

```yaml
service: servo_cam.move_servo
data:
  pan: 90    # 0-180°
  tilt: 165  # 0-180°
```

**Use Case**: Point camera at specific location based on automation logic.

#### `servo_cam.preset_position`
Quick movement to named positions.

```yaml
service: servo_cam.preset_position
data:
  position: top_right  # See preset list below
```

**Available Presets**:
- `center`: Middle position (90°, 165°)
- `left`: Left side (30°, 165°)
- `right`: Right side (150°, 165°)
- `up`: Look up (90°, 150°)
- `down`: Look down (90°, 180°)
- `top_left`: Upper left corner (30°, 150°)
- `top_right`: Upper right corner (150°, 150°)
- `bottom_left`: Lower left corner (30°, 180°)
- `bottom_right`: Lower right corner (150°, 180°)

**Use Case**: Quick camera movements in automations without calculating angles.

#### `servo_cam.center_camera`
Shortcut to center position.

```yaml
service: servo_cam.center_camera
```

### Control Services

#### `servo_cam.start_patrol`
Begin autonomous scanning.

```yaml
service: servo_cam.start_patrol
```

**Requirements**: Monitoring must be active first.

#### `servo_cam.stop_patrol`
Stop autonomous scanning.

```yaml
service: servo_cam.stop_patrol
```

## Automation Blueprints

### Blueprint 1: Motion-Based Recording

```yaml
blueprint:
  name: Security Camera Motion Recording
  description: Start recording when motion detected with high threat level
  domain: automation
  input:
    threat_threshold:
      name: Threat Level Threshold
      description: Minimum threat level to trigger (0.0-1.0)
      default: 0.6
      selector:
        number:
          min: 0.0
          max: 1.0
          step: 0.1
    classification:
      name: Motion Classification
      description: Type of motion to trigger on
      default: person
      selector:
        select:
          options:
            - person
            - vehicle
            - animal
            - any

automation:
  trigger:
    - platform: state
      entity_id: binary_sensor.servo_cam_motion_detected
      to: "on"
  condition:
    - condition: numeric_state
      entity_id: sensor.servo_cam_last_motion_threat_level
      above: !input threat_threshold
    - condition: template
      value_template: >
        {% set classification = !input classification %}
        {% if classification == 'any' %}
          true
        {% else %}
          {{ state_attr('sensor.servo_cam_last_motion_classification', 'classification') == classification }}
        {% endif %}
  action:
    - service: camera.record
      data:
        entity_id: camera.servo_security_camera
        filename: "/media/security/motion_{{ now().strftime('%Y%m%d_%H%M%S') }}.mp4"
        duration: 30
```

### Blueprint 2: Scheduled Patrol

```yaml
blueprint:
  name: Security Camera Scheduled Patrol
  description: Run patrol mode during specific hours
  domain: automation
  input:
    start_time:
      name: Start Time
      description: When to start patrol
      default: "22:00:00"
      selector:
        time:
    end_time:
      name: End Time
      description: When to stop patrol
      default: "06:00:00"
      selector:
        time:

automation:
  - alias: Start Patrol
    trigger:
      - platform: time
        at: !input start_time
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.servo_cam_monitoring
      - delay: 5
      - service: servo_cam.start_patrol

  - alias: Stop Patrol
    trigger:
      - platform: time
        at: !input end_time
    action:
      - service: servo_cam.stop_patrol
      - delay: 5
      - service: switch.turn_off
        target:
          entity_id: switch.servo_cam_monitoring
```

## Advanced Lovelace Cards

### Full Control Dashboard

```yaml
title: Security Camera Control
type: vertical-stack
cards:
  # Live View
  - type: picture-entity
    entity: camera.servo_security_camera
    camera_view: live
    aspect_ratio: 4:3

  # Quick Status
  - type: glance
    entities:
      - entity: binary_sensor.servo_cam_monitoring_active
        name: Monitoring
      - entity: binary_sensor.servo_cam_patrol_active
        name: Patrol
      - entity: binary_sensor.servo_cam_motion_detected
        name: Motion
      - entity: sensor.servo_cam_last_motion_threat_level
        name: Threat
    show_state: true

  # Controls
  - type: horizontal-stack
    cards:
      - type: button
        entity: switch.servo_cam_monitoring
        name: Monitoring
        icon: mdi:eye
        tap_action:
          action: toggle

      - type: button
        entity: switch.servo_cam_patrol_mode
        name: Patrol
        icon: mdi:routes
        tap_action:
          action: toggle

      - type: button
        name: Center
        icon: mdi:target
        tap_action:
          action: call-service
          service: servo_cam.center_camera

  # D-Pad Control
  - type: grid
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

  # Detailed Stats
  - type: entities
    title: Camera Statistics
    entities:
      - entity: sensor.servo_cam_pan_angle
      - entity: sensor.servo_cam_tilt_angle
      - entity: sensor.servo_cam_motion_detections
      - entity: sensor.servo_cam_alerts_sent
      - entity: sensor.servo_cam_session_duration
      - entity: sensor.servo_cam_frames_processed
      - entity: sensor.servo_cam_last_motion_classification
      - entity: sensor.servo_cam_alert_queue_size

  # Motion History Graph
  - type: history-graph
    title: Motion Activity
    entities:
      - entity: binary_sensor.servo_cam_motion_detected
      - entity: sensor.servo_cam_last_motion_threat_level
    hours_to_show: 6
```

### Minimal Status Card

```yaml
type: entities
title: Security Camera
entities:
  - entity: camera.servo_security_camera
  - type: divider
  - entity: switch.servo_cam_monitoring
    secondary_info: last-changed
  - entity: binary_sensor.servo_cam_motion_detected
    secondary_info: last-changed
  - entity: sensor.servo_cam_last_motion_classification
  - type: divider
  - entity: sensor.servo_cam_pan_angle
    name: Position
    format: precision1
    secondary_info: >
      {{ states('sensor.servo_cam_tilt_angle') }}°
```

## Performance Tuning

### Reduce Update Frequency

Edit `/custom_components/servo_cam/const.py`:

```python
UPDATE_INTERVAL = 2  # Increase from 1 to 2 seconds
```

Benefits: Lower CPU usage on both HA and Raspberry Pi
Trade-off: Slightly delayed sensor updates

### Disable Unused Sensors

If you don't need all sensors, comment them out in `sensor.py`:

```python
sensors = [
    PanAngleSensor(coordinator, entry),
    TiltAngleSensor(coordinator, entry),
    # WebhookQueueSensor(coordinator, entry),  # Disabled
]
```

### Optimize Streaming

For lower bandwidth, adjust camera quality in servo-cam `config/settings.py`:

```python
CAMERA_JPEG_QUALITY = 60  # Lower from 75
CAMERA_FPS = 10  # Lower from 15
```

## Troubleshooting

### Common Issues

#### 1. Integration Not Loading

**Symptom**: Integration doesn't appear in UI

**Solutions**:
- Check logs: Settings → System → Logs
- Verify directory structure: `/config/custom_components/servo_cam/`
- Ensure `manifest.json` is valid JSON
- Restart Home Assistant completely

#### 2. Connection Failed

**Symptom**: "Cannot connect" error during setup

**Solutions**:
- Verify servo-cam is running: `systemctl status security-cam`
- Test API directly: `curl http://<ip>:5000/healthz`
- Check firewall: `sudo ufw allow 5000`
- Verify network connectivity between HA and Pi

#### 3. Camera Stream Not Loading

**Symptom**: Black screen or "Camera not available"

**Solutions**:
- Ensure monitoring is ON: `switch.servo_cam_monitoring`
- Check camera is active: `binary_sensor.servo_cam_camera_active`
- Test stream directly: `http://<ip>:5000/video_feed`
- Review servo-cam logs: `journalctl -u security-cam -f`

#### 4. Entities Not Updating

**Symptom**: Sensors show "Unknown" or don't update

**Solutions**:
- Check coordinator status in integration page
- Verify `/status` endpoint returns valid JSON
- Increase update interval if overloaded
- Review Home Assistant logs for API errors

#### 5. Services Not Working

**Symptom**: Service calls fail or timeout

**Solutions**:
- Verify servo is connected: `binary_sensor.servo_cam_servo_connected`
- Check servo hardware: `sudo i2cdetect -y 1`
- Test manual API call: `curl -X POST http://<ip>:5000/servo/move -d '{"pan":90,"tilt":165}'`
- Review servo-cam logs for hardware errors

### Debug Mode

Enable debug logging for integration:

Edit `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.servo_cam: debug
    aiohttp: debug
```

Restart and check logs for detailed information.

### Health Check Script

Create a health check automation:

```yaml
automation:
  - alias: "Camera Health Check"
    trigger:
      - platform: time_pattern
        minutes: "/5"
    action:
      - service: system_log.write
        data:
          message: >
            Camera Health:
            Monitoring={{ states('binary_sensor.servo_cam_monitoring_active') }}
            Camera={{ states('binary_sensor.servo_cam_camera_active') }}
            Servo={{ states('binary_sensor.servo_cam_servo_connected') }}
            Queue={{ states('sensor.servo_cam_alert_queue_size') }}
          level: info
```

## Security Considerations

### Network Security

- Use private network for camera system
- Consider VPN for remote access
- Implement firewall rules limiting port 5000 access
- Use HTTPS reverse proxy (nginx, Traefik) if exposing externally

### Authentication

Current implementation has no authentication. For production:

1. Add authentication to Flask API in `main.py`:

```python
from flask_httpauth import HTTPBasicAuth
auth = HTTPBasicAuth()

@auth.verify_password
def verify_password(username, password):
    # Implement authentication logic
    pass

@app.route('/status')
@auth.login_required
def status():
    # ...
```

2. Update coordinator to include auth headers

### Privacy

- Motion detection stores no images (only metadata)
- Webhooks include base64 snapshots (ensure secure webhook endpoint)
- Consider disabling external webhooks if using HA only
- Review logs regularly for unauthorized access attempts

## Future Enhancements

Planned features:

- [ ] WebRTC streaming support (lower latency)
- [ ] Multi-camera support
- [ ] Recording integration with Home Assistant media browser
- [ ] Custom event triggers for automations
- [ ] Mobile app notifications with snapshots
- [ ] Integration with Frigate NVR
- [ ] TensorFlow Lite object detection option
- [ ] Zone-based motion detection
- [ ] Time-lapse generation
- [ ] Cloud backup integration

## Contributing

See main repository for contribution guidelines.

## License

MIT License - see main repository LICENSE file.

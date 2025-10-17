# Home Assistant Integration - Quick Reference

Fast lookup guide for common tasks.

## Installation

1. **Add repository**: Settings → Add-ons → Add-on Store → ⋮ → Repositories → `https://github.com/lazarevtill/Servo-Cam`
2. **Install & start**: Select **Servo Cam** → Install → Start (optionally enable auto-start/watchdog)
3. **Confirm discovery**: Keep `python3 main.py` or the add-on running so Zeroconf stays online, then accept the "New device discovered" prompt
   - *`mode: local` targets Home Assistant OS/Supervised on Raspberry Pi (ARM). For x86 installs, set `mode: remote` and enter the Raspberry Pi address where you ran `install.sh`.*

## Entity IDs

| Type | Entity ID | Description |
|------|-----------|-------------|
| Camera | `camera.servo_security_camera` | Live stream + snapshot |
| Sensor | `sensor.servo_cam_pan_angle` | Pan position (°) |
| Sensor | `sensor.servo_cam_tilt_angle` | Tilt position (°) |
| Sensor | `sensor.servo_cam_motion_detections` | Motion count |
| Sensor | `sensor.servo_cam_alerts_sent` | Alert count |
| Sensor | `sensor.servo_cam_session_duration` | Session time (s) |
| Sensor | `sensor.servo_cam_frames_processed` | Frame count |
| Sensor | `sensor.servo_cam_last_motion_classification` | Motion type |
| Sensor | `sensor.servo_cam_last_motion_threat_level` | Threat (0-1) |
| Sensor | `sensor.servo_cam_alert_queue_size` | Queue size |
| Binary | `binary_sensor.servo_cam_monitoring_active` | Is monitoring |
| Binary | `binary_sensor.servo_cam_patrol_active` | Is patrolling |
| Binary | `binary_sensor.servo_cam_servo_connected` | Servo online |
| Binary | `binary_sensor.servo_cam_camera_active` | Camera online |
| Binary | `binary_sensor.servo_cam_motion_detected` | Motion now |
| Switch | `switch.servo_cam_monitoring` | Control monitoring |
| Switch | `switch.servo_cam_patrol_mode` | Control patrol |

## Services

### Move to Angles
```yaml
service: servo_cam.move_servo
data:
  pan: 90   # 0-180
  tilt: 165 # 0-180
```

### Move to Preset
```yaml
service: servo_cam.preset_position
data:
  position: center  # or left, right, up, down, top_left, etc.
```

### Control Patrol
```yaml
service: servo_cam.start_patrol  # Start scanning
service: servo_cam.stop_patrol   # Stop scanning
service: servo_cam.center_camera # Quick center
```

## Preset Positions

| Name | Pan | Tilt |
|------|-----|------|
| `center` | 90° | 165° |
| `left` | 30° | 165° |
| `right` | 150° | 165° |
| `up` | 90° | 150° |
| `down` | 90° | 180° |
| `top_left` | 30° | 150° |
| `top_right` | 150° | 150° |
| `bottom_left` | 30° | 180° |
| `bottom_right` | 150° | 180° |

## Common Automations

### Start at Sunset
```yaml
automation:
  trigger:
    platform: sun
    event: sunset
  action:
    service: switch.turn_on
    target:
      entity_id: switch.servo_cam_monitoring
```

### Alert on Person
```yaml
automation:
  trigger:
    platform: state
    entity_id: binary_sensor.servo_cam_motion_detected
    to: "on"
  condition:
    - "{{ state_attr('sensor.servo_cam_last_motion_classification', 'classification') == 'person' }}"
  action:
    service: notify.mobile_app
    data:
      message: "Person detected!"
```

### High Threat Alert
```yaml
automation:
  trigger:
    platform: numeric_state
    entity_id: sensor.servo_cam_last_motion_threat_level
    above: 0.7
  action:
    service: notify.telegram
    data:
      message: "High threat detected!"
```

### Move on Door Open
```yaml
automation:
  trigger:
    platform: state
    entity_id: binary_sensor.front_door
    to: "on"
  action:
    service: servo_cam.move_servo
    data:
      pan: 120
      tilt: 165
```

### Night Patrol
```yaml
automation:
  trigger:
    platform: time
    at: "22:00:00"
  action:
    - service: switch.turn_on
      target:
        entity_id: switch.servo_cam_monitoring
    - delay: 5
    - service: servo_cam.start_patrol
```

## Lovelace Cards

### Minimal
```yaml
type: picture-entity
entity: camera.servo_security_camera
camera_view: live
```

### With Controls
```yaml
type: vertical-stack
cards:
  - type: picture-entity
    entity: camera.servo_security_camera
    camera_view: live
  - type: entities
    entities:
      - switch.servo_cam_monitoring
      - switch.servo_cam_patrol_mode
      - sensor.servo_cam_pan_angle
      - sensor.servo_cam_tilt_angle
```

### D-Pad
```yaml
type: grid
columns: 3
cards:
  - type: button
    icon: mdi:arrow-top-left
    tap_action:
      action: call-service
      service: servo_cam.preset_position
      data:
        position: top_left
  # ... (8 more buttons)
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Integration not found | Copy files, restart HA |
| Cannot connect | Check Pi IP, port 5000, firewall |
| No camera stream | Enable monitoring switch |
| Services missing | Restart HA after install |
| Entities unavailable | Check Pi is running, test /healthz |

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/healthz` | GET | Health check |
| `/status` | GET | System status |
| `/snapshot` | GET | Camera image |
| `/video_feed` | GET | MJPEG stream |
| `/monitoring/start` | POST | Start monitoring |
| `/monitoring/stop` | POST | Stop monitoring |
| `/servo/move` | POST | Move servos |
| `/config` | GET/POST | Configuration |

## Configuration

Default update interval: **1 second**

Edit `/custom_components/servo_cam/const.py`:
```python
UPDATE_INTERVAL = 1  # seconds
```

Default connection:
- Host: `localhost`
- Port: `5000`

## Performance

- RAM: ~5-10 MB
- CPU: <1% idle, ~2-3% active
- Network: ~5 KB/s status, ~500 KB/s streaming
- Latency: 60-125 ms updates

## File Locations

```
/config/custom_components/servo_cam/
├── __init__.py           # Main integration
├── config_flow.py        # UI setup
├── coordinator.py        # Data updates
├── camera.py             # Camera entity
├── sensor.py             # 9 sensors
├── binary_sensor.py      # 5 binary sensors
├── switch.py             # 2 switches
├── services.yaml         # Service definitions
└── manifest.json         # Integration metadata
```

## Supported Features

- ✅ Live MJPEG streaming
- ✅ Snapshot capture
- ✅ Pan/tilt control (0-180°)
- ✅ 9 preset positions
- ✅ Autonomous patrol
- ✅ Motion detection
- ✅ Threat level assessment
- ✅ Motion classification
- ✅ Scene change detection
- ✅ Priority-based alerts
- ✅ Automation support
- ✅ Lovelace cards

## Not Supported

- ❌ Two-way audio
- ❌ WebRTC streaming (yet)
- ❌ Recording (use HA recorder)
- ❌ Authentication (add reverse proxy)
- ❌ HTTPS (use reverse proxy)
- ❌ Multi-camera (one integration per camera)

## Documentation

- Full guide: `HOMEASSISTANT_INTEGRATION.md`
- Architecture: `HA_INTEGRATION_ARCHITECTURE.md`
- Summary: `INTEGRATION_SUMMARY.md`
- Integration README: `custom_components/servo_cam/README.md`

## Support

1. Check logs: Settings → System → Logs
2. Test API: `curl http://<ip>:5000/healthz`
3. Verify servo-cam: `systemctl status servo-cam.service`
4. Review integration status: Settings → Devices & Services

## Version Info

- Integration version: **1.1.0**
- Domain: `servo_cam`
- Platforms: camera, sensor, binary_sensor, switch
- Update method: polling (1s)
- IoT class: `local_push`

---

**Quick Start**: Add repo `https://github.com/lazarevtill/Servo-Cam` → Install & start add-on → Accept discovery prompt

**Common Use**: Turn on monitoring switch → Camera starts → View in dashboard → Move with presets

**Automations**: Trigger on `binary_sensor.motion_detected` or `sensor.threat_level` → Take action

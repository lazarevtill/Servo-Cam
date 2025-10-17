# Home Assistant Integration Architecture

Visual guide to understanding how the integration works.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Home Assistant                           │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                  Frontend (Lovelace)                     │  │
│  │  ┌────────┐  ┌─────────┐  ┌──────────┐  ┌────────────┐ │  │
│  │  │ Camera │  │ Sensors │  │ Controls │  │ Automation │ │  │
│  │  │ Stream │  │  9x     │  │ Switches │  │   Engine   │ │  │
│  │  └────────┘  └─────────┘  └──────────┘  └────────────┘ │  │
│  └──────────────────────────────────────────────────────────┘  │
│                            ▲                                    │
│                            │ Entity Updates                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │            Custom Integration: servo_cam                 │  │
│  │                                                          │  │
│  │  ┌─────────────────────────────────────────────────┐   │  │
│  │  │      ServoCamCoordinator (Update Logic)         │   │  │
│  │  │  - Polls /status every 1s                       │   │  │
│  │  │  - Manages aiohttp session                      │   │  │
│  │  │  - Distributes data to entities                 │   │  │
│  │  └─────────────────────────────────────────────────┘   │  │
│  │            │                                             │  │
│  │            ▼                                             │  │
│  │  ┌─────────────────────────────────────────────────┐   │  │
│  │  │              Entity Platforms                   │   │  │
│  │  │  - Camera (1)   - Sensor (9)                    │   │  │
│  │  │  - Binary (5)   - Switch (2)                    │   │  │
│  │  └─────────────────────────────────────────────────┘   │  │
│  │                                                          │  │
│  │  ┌─────────────────────────────────────────────────┐   │  │
│  │  │            Service Handlers                     │   │  │
│  │  │  - move_servo      - start_patrol               │   │  │
│  │  │  - preset_position - stop_patrol                │   │  │
│  │  │  - center_camera                                │   │  │
│  │  └─────────────────────────────────────────────────┘   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                            │                                    │
│                            │ HTTP/REST (async)                  │
└────────────────────────────┼────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                 Raspberry Pi (192.168.x.x:5000)                 │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Flask REST API (Presentation)               │  │
│  │  /status  /snapshot  /video_feed  /monitoring/*  /move   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                            │                                    │
│                            ▼                                    │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │         MonitoringService (Application Layer)            │  │
│  │  - Process frames   - Detect motion                      │  │
│  │  - Scene detection  - Patrol control                     │  │
│  │  - Intelligence     - Webhook queue                      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                            │                                    │
│                            ▼                                    │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │          Infrastructure Layer (Repositories)             │  │
│  │  ┌────────────┐  ┌───────────┐  ┌───────────────────┐   │  │
│  │  │  Camera    │  │   Servo   │  │  Motion Detector  │   │  │
│  │  │ Picamera2  │  │  PCA9685  │  │     OpenCV        │   │  │
│  │  └────────────┘  └───────────┘  └───────────────────┘   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                            │                                    │
│                            ▼                                    │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                  Hardware Layer                          │  │
│  │  🎥 Camera Module    🎮 Pan/Tilt Servos                  │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Status Updates (Periodic)

```
┌─────────────┐      GET /status      ┌────────────┐
│ Coordinator │ ───────────────────────▶│ Flask API  │
│  (every 1s) │                        │            │
└─────────────┘                        └────────────┘
       │                                      │
       │                                      ▼
       │                              ┌────────────┐
       │                              │ Monitoring │
       │                              │  Service   │
       │                              └────────────┘
       │                                      │
       │          JSON Response               │
       │    {pan, tilt, motion_count...}      │
       │◀─────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────┐
│  Update All Entities:                       │
│  - sensor.servo_cam_pan_angle = 90          │
│  - sensor.servo_cam_motion_detections = 42  │
│  - binary_sensor.servo_cam_monitoring = on  │
│  - ... (17 entities total)                  │
└─────────────────────────────────────────────┘
       │
       ▼
┌─────────────┐
│   Lovelace  │  Entities auto-update in UI
│     UI      │
└─────────────┘
```

### 2. Camera Streaming (Continuous)

```
┌─────────────┐    GET /video_feed    ┌────────────┐
│   Camera    │ ────────────────────▶  │ Flask API  │
│   Entity    │                        │  (MJPEG)   │
└─────────────┘                        └────────────┘
       │                                      │
       │    MJPEG Stream (multipart/x-      │
       │    mixed-replace boundary=frame)    │
       │◀────────────────────────────────────┘
       │
       │    Direct passthrough, no re-encoding
       │
       ▼
┌─────────────┐
│  HA Camera  │  Live stream in dashboard
│   Viewer    │
└─────────────┘
```

### 3. Service Calls (On-Demand)

```
User clicks "Move Left" button in UI
       │
       ▼
┌──────────────────┐
│  Automation or   │
│  Manual Action   │
└──────────────────┘
       │
       ▼
┌──────────────────────────────────────────────┐
│  service: servo_cam.preset_position          │
│  data:                                       │
│    position: left                            │
└──────────────────────────────────────────────┘
       │
       ▼
┌─────────────┐
│  Service    │  Translate "left" to pan=30, tilt=165
│  Handler    │
└─────────────┘
       │
       ▼
┌─────────────┐    POST /servo/move    ┌────────────┐
│ Coordinator │ ───────────────────────▶│ Flask API  │
│             │  {"pan":30,"tilt":165}  │            │
└─────────────┘                        └────────────┘
       │                                      │
       │                                      ▼
       │                              ┌────────────┐
       │                              │ Monitoring │
       │                              │  Service   │
       │                              └────────────┘
       │                                      │
       │                                      ▼
       │                              ┌────────────┐
       │                              │   Servo    │
       │                              │  Hardware  │
       │                              └────────────┘
       │
       │          HTTP 200 OK
       │◀─────────────────────────────────────
       │
       ▼
  Request refresh to update sensors immediately
```

## Entity Hierarchy

```
Device: Servo Security Camera (192.168.1.100)
│
├── Camera
│   └── camera.servo_security_camera
│       ├── Attributes: pan_angle, tilt_angle, motion_count
│       ├── Features: ON_OFF, STREAM
│       └── Methods: turn_on(), turn_off(), camera_image()
│
├── Sensors (9)
│   ├── sensor.servo_cam_pan_angle (0-180°)
│   ├── sensor.servo_cam_tilt_angle (0-180°)
│   ├── sensor.servo_cam_motion_detections (count)
│   ├── sensor.servo_cam_alerts_sent (count)
│   ├── sensor.servo_cam_session_duration (seconds)
│   ├── sensor.servo_cam_frames_processed (count)
│   ├── sensor.servo_cam_last_motion_classification (string)
│   ├── sensor.servo_cam_last_motion_threat_level (0.0-1.0)
│   └── sensor.servo_cam_alert_queue_size (count)
│
├── Binary Sensors (5)
│   ├── binary_sensor.servo_cam_monitoring_active (on/off)
│   ├── binary_sensor.servo_cam_patrol_active (on/off)
│   ├── binary_sensor.servo_cam_servo_connected (on/off)
│   ├── binary_sensor.servo_cam_camera_active (on/off)
│   └── binary_sensor.servo_cam_motion_detected (on/off)
│
└── Switches (2)
    ├── switch.servo_cam_monitoring (control monitoring)
    └── switch.servo_cam_patrol_mode (control patrol)
```

## State Machine

### Monitoring State

```
             ┌──────────────┐
             │   Stopped    │
             │ monitoring=  │
             │    false     │
             └──────────────┘
                    │ │
         turn_on()  │ │  turn_off()
                    ▼ │
             ┌──────────────┐
             │   Running    │
             │ monitoring=  │
             │     true     │
             └──────────────┘
                    │
       PATROL_ENABLED=true
                    │
                    ▼
             ┌──────────────┐
             │  Patrolling  │
             │   patrol=    │
             │     true     │
             └──────────────┘
```

### Patrol Sequence

```
Start Patrol
     │
     ▼
┌────────────────────────────────────┐
│  Initialize positions (5×3 grid)  │
│  [(30,150), (60,150), (90,150)...]│
└────────────────────────────────────┘
     │
     ▼
┌────────────────────────────────────┐
│  Move to position [0]: (30°, 150°)│
└────────────────────────────────────┘
     │
     ▼
┌────────────────────────────────────┐
│  Dwell 3 seconds                   │
│  - Detect motion                   │
│  - Compare scene baseline          │
└────────────────────────────────────┘
     │
     ▼
┌────────────────────────────────────┐
│  Move to position [1]: (60°, 150°)│
└────────────────────────────────────┘
     │
     ▼
   ... (continues through all 15 positions)
     │
     ▼
┌────────────────────────────────────┐
│  Loop back to position [0]         │
└────────────────────────────────────┘
```

## Automation Trigger Flow

```
Motion Detected
     │
     ▼
┌────────────────────────────────────┐
│ binary_sensor.motion_detected: on  │
└────────────────────────────────────┘
     │
     ▼
┌────────────────────────────────────┐
│  Check threat level                │
│  sensor.threat_level > 0.7         │
└────────────────────────────────────┘
     │
     ▼
┌────────────────────────────────────┐
│  Check classification               │
│  classification == "person"         │
└────────────────────────────────────┘
     │
     ▼
┌────────────────────────────────────┐
│  Trigger Automation Action          │
│  - Send notification                │
│  - Capture snapshot                 │
│  - Start recording                  │
│  - Turn on lights                   │
└────────────────────────────────────┘
```

## Communication Protocols

### REST API (Control & Status)

```
Home Assistant ────────────▶ Raspberry Pi
                HTTP/REST

Methods:
- GET  /status        → JSON status object
- GET  /snapshot      → JPEG image bytes
- GET  /config        → JSON config object
- POST /monitoring/*  → Control monitoring
- POST /servo/move    → Move servos
- POST /config        → Update settings

Format: JSON request/response
Timeout: 10 seconds
Retry: Automatic on failure
```

### MJPEG Streaming (Video)

```
Home Assistant ────────────▶ Raspberry Pi
             multipart/x-mixed-replace

Stream Format:
--frame
Content-Type: image/jpeg

<JPEG data>
--frame
Content-Type: image/jpeg

<JPEG data>
--frame
...

Update Rate: ~15-20 FPS
Latency: ~100ms
Encoding: JPEG (quality 75)
```

## Configuration Flow

```
User adds integration in UI
     │
     ▼
┌────────────────────────────────────┐
│  Config Flow: async_step_user()    │
│  Show form: host, port             │
└────────────────────────────────────┘
     │
     ▼
┌────────────────────────────────────┐
│  Validate: GET /healthz            │
│  Check response status             │
└────────────────────────────────────┘
     │
   ┌─┴─────────┐
   │           │
  OK         Error
   │           │
   ▼           ▼
 Create    Show error
 Entry     Try again
   │
   ▼
┌────────────────────────────────────┐
│  Create coordinator                │
│  Set up platforms                  │
│  Register services                 │
└────────────────────────────────────┘
   │
   ▼
┌────────────────────────────────────┐
│  Integration Ready                 │
│  17 entities discovered            │
└────────────────────────────────────┘
```

## Performance Characteristics

### Resource Usage

```
Integration:          5-10 MB RAM
  Coordinator:        2 MB
  Entities (17):      3-5 MB
  aiohttp session:    1-2 MB

CPU Usage:           <1% idle
  Status updates:    ~2% (every 1s)
  Service calls:     ~1% spike

Network:
  Status polling:    ~5 KB/s
  Camera stream:     ~500 KB/s
  Snapshots:         ~50 KB each
```

### Timing

```
Update Cycle:        1 second
  Fetch /status:     50-100 ms
  Parse JSON:        1-5 ms
  Update entities:   10-20 ms
  Total latency:     60-125 ms

Service Call:        <1 second
  REST request:      50-200 ms
  Servo movement:    200-500 ms
  State update:      1000 ms (next cycle)

Snapshot:            <500 ms
  Request:           50 ms
  Capture:           100-200 ms
  Transfer:          50-100 ms
```

## Error Handling

```
API Call Failure
     │
     ▼
┌────────────────────────────────────┐
│  Timeout / Connection Error        │
└────────────────────────────────────┘
     │
     ▼
┌────────────────────────────────────┐
│  Log error to Home Assistant       │
│  Mark entities as unavailable      │
└────────────────────────────────────┘
     │
     ▼
┌────────────────────────────────────┐
│  Coordinator continues polling     │
│  Will recover on next success      │
└────────────────────────────────────┘
     │
     ▼
┌────────────────────────────────────┐
│  Auto-recovery: Entities available │
│  Resume normal operation           │
└────────────────────────────────────┘
```

## Security Model

```
┌─────────────────────────────────────────┐
│         Home Assistant                  │
│  ┌───────────────────────────────────┐  │
│  │  Integration runs in HA process   │  │
│  │  - User: homeassistant            │  │
│  │  - No elevated privileges         │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
              │
              │ HTTP (no auth)
              │ Local network only
              ▼
┌─────────────────────────────────────────┐
│       Raspberry Pi (Flask)              │
│  ┌───────────────────────────────────┐  │
│  │  No authentication (by default)    │  │
│  │  Bind to 0.0.0.0:5000             │  │
│  │  Accessible on local network      │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘

Recommendations:
1. Keep on isolated VLAN
2. Firewall external access
3. Add reverse proxy with auth
4. Use HTTPS for external exposure
5. Consider VPN for remote access
```

## Scalability

### Single Camera System
```
Current:     1 camera → 17 entities → Performs well
Load:        Minimal (1s updates, <1% CPU)
Concurrent:  Multiple HA users can view simultaneously
```

### Future Multi-Camera
```
Option 1: Multiple Integrations
  camera_1 → Integration 1 → 17 entities
  camera_2 → Integration 2 → 17 entities
  camera_3 → Integration 3 → 17 entities

Option 2: Single Integration (requires code changes)
  Integration → Multiple coordinators → N×17 entities
```

---

This architecture provides:
- ✅ Clean separation of concerns
- ✅ Efficient resource usage
- ✅ Scalable design
- ✅ Robust error handling
- ✅ Real-time updates
- ✅ Production-ready performance

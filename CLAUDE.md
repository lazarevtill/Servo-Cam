# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A production-ready Raspberry Pi security camera system with motion tracking, servo control, and webhook notifications. Built with **Domain-Driven Design (DDD)** and **KISS (Keep It Simple, Stupid)** principles for maintainability and extensibility.

## Architecture: DDD with Clean Architecture

The codebase follows strict layered architecture with dependency inversion:

```
domain/ (innermost)
  ↑
application/
  ↑
infrastructure/
  ↑
presentation/ (outermost)
```

### Core Architectural Patterns

**1. Domain Layer** (`domain/`)
- **Entities** (`domain/entities/`): Objects with identity that change over time
  - `Camera`: Tracks camera state, frame count, activation
  - `ServoController`: Manages servo positions, connection state, position history
  - `MonitoringSession`: Represents an active security monitoring session with statistics
- **Value Objects** (`domain/value_objects/`): Immutable, compared by value
  - `Angle`: Validated 0-180° angle with difference calculations
  - `ServoPosition`: Immutable pan/tilt position with timestamp
  - `MotionDetection`: Intelligent motion detection result with:
    - Base properties: area, center, bounding box, confidence
    - Shape analysis: aspect_ratio, compactness
    - Motion dynamics: velocity_x/y, speed, persistence
    - Intelligence: classification, threat_level, frame_brightness
    - Computed properties: is_significant, requires_immediate_attention
  - `Frame`: Camera frame wrapper with metadata
  - `WebhookPayload`: Webhook data structure with serialization (includes scene-change and motion intelligence metadata)
- **Repository Interfaces** (`domain/repositories/`): Abstract contracts (dependency inversion)
  - `ICameraRepository`: Camera hardware abstraction
  - `IServoRepository`: Servo control abstraction
  - `IMotionDetector`: Motion detection abstraction
  - `IWebhookRepository`: Webhook notification abstraction

**2. Application Layer** (`application/services/`)
- **MonitoringService**: Orchestrates all domain logic
  - Frame processing pipeline: capture → detect motion → analyze intelligence → filter webhooks (NO servo tracking)
  - **Autonomous Patrol Mode**: Camera continuously scans predefined positions to monitor for scene changes
  - **Motion tracking DISABLED**: Camera does NOT follow motion, only logs it
  - Motion detection runs but servos only move during patrol
  - Manual control mode (bypasses monitoring and patrol)
  - Scene change detector maintains per-angle baselines with brightness normalization
  - Intelligent motion analysis with classification and threat-based filtering
- **MotionIntelligence**: Enhances motion detection with multi-dimensional analysis
  - Motion classification (person, vehicle, animal, environmental)
  - Threat level assessment (0.0-1.0) based on context
  - Trajectory tracking and oscillation detection
  - Adaptive confidence validation with lighting awareness
  - Multi-frame persistence tracking
- **SceneChangeDetector**: Monitors for structural changes independent of lighting
  - Brightness-normalized comparison (lighting changes vs. scene changes)
  - Adaptive baseline blending (3x faster during lighting shifts)
  - Per-position cooldown to prevent spam

**3. Infrastructure Layer** (`infrastructure/`)
- **Camera Implementations** (`infrastructure/camera/`):
  - `PiCameraRepository`: Picamera2 implementation (preferred)
  - `V4L2CameraRepository`: OpenCV V4L2 fallback
  - `OpenCVMotionDetector`: Background subtraction with morphological filtering
  - Both apply flip/rotation transforms from settings
- **Servo Implementation** (`infrastructure/servo/`):
  - `PCA9685ServoRepository`: Hardware I2C servo control
  - `MockServoRepository`: Testing without hardware
- **Webhook Implementation** (`infrastructure/webhook/`):
  - `HTTPWebhookRepository`: Async queue-based webhook sender
  - Background worker thread with cooldown

**4. Presentation Layer** (`presentation/`)
- **API Routes** (`presentation/api/routes.py`): Flask REST endpoints
- **Templates** (`presentation/templates/`): Web UI with D-pad controls

### Critical Architectural Rules

1. **Dependencies flow inward only**: `presentation` → `infrastructure` → `application` → `domain`
2. **Domain layer has ZERO external dependencies**: No Flask, OpenCV, or hardware imports
3. **Dependency Injection**: All repositories injected into MonitoringService (see `main.py:108-113`)
4. **Interface segregation**: Each repository has single, focused responsibility
5. **Value objects are immutable**: Use `@dataclass(frozen=True)`

## Running the Application

### Development
```bash
source venv/bin/activate
python3 main.py
```

### Production (systemd)
```bash
sudo systemctl start security-cam
sudo journalctl -u security-cam -f  # View logs
```

### Testing Individual Components
```bash
# Test camera
python3 -c "from infrastructure.camera import PiCameraRepository; cam = PiCameraRepository(); print('OK' if cam.start() else 'FAIL'); cam.stop()"

# Test servo I2C
sudo i2cdetect -y 1  # Should show 0x40

# Test webhook
curl -X POST http://localhost:5000/status
```

## Configuration Management

**Primary source**: `config/settings.py` (class-based settings)
**Override mechanism**: Environment variables take precedence

Key settings:
- `CAMERA_FLIP_HORIZONTAL/VERTICAL`: Applied in camera repositories (lines 112-121 in picamera_repository.py)
- `MIN_AREA_RATIO`: Motion detection sensitivity (lower = more sensitive)
- `WEBHOOK_ANGLE_THRESHOLD`: Minimum servo movement to trigger webhook
- `EMA_ALPHA`: Tracking smoothness (0.25 = smooth, higher = more responsive)
- `BUTTON_STEP_SIZE`: Degrees per D-pad button press
- `SCENE_*`: Configure per-angle scene baseline comparison and alert thresholds
- `MOTION_INTELLIGENCE_ENABLED`: Enable intelligent motion analysis (default: true)
- `WEBHOOK_SEND_LOW_PRIORITY`: Send low-priority motion alerts (default: false)
- `WEBHOOK_SUPPRESS_ENVIRONMENTAL`: Suppress environmental motion webhooks (default: true)

**Dynamic configuration**: POST to `/config` endpoint updates settings at runtime (doesn't persist across restarts)

## Key Implementation Details

### Patrol-Only Monitoring Pipeline (application/services/monitoring_service.py)

**IMPORTANT: Motion tracking is DISABLED - camera only moves during patrol**

**Every Frame:**
```
1. capture_frame() → Frame
2. motion_detector.detect(frame) → MotionDetection (with shape analysis + brightness)
3. motion_intelligence.analyze(motion) → Enhanced MotionDetection (classification, threat level)
4. Filter webhooks by priority (suppress environmental motion, low confidence)
5. Compare current frame against scene baseline (brightness-normalized)
6. Execute patrol movement (continuous, independent of motion):
   - Move through pan×tilt grid (default 15 positions)
   - For each tilt level, sweep through all pan positions
   - Dwell at each position for PATROL_DWELL_TIME (default 3s)
   - Scene change detection runs at each position (structural changes only)
   - Grid pattern: (30°,150°) → (60°,150°) → (90°,150°) → (120°,150°) → (150°,150°)
                 → (30°,165°) → (60°,165°) → ... → (150°,180°) → repeat
```

**Patrol Disabled:**
```
Camera stays centered, no autonomous movement
Motion still detected and logged
```

### Servo Position Tracking
- `ServoController.current_position`: Current known position
- `_position_history`: Deque of last 10 positions for webhook comparison
- `get_previous_position()`: Used to calculate angle deltas for webhooks

### Camera Frame Processing
- Background thread continuously captures frames (infrastructure/camera/picamera_repository.py:101-147)
- Applies flip/rotation transforms BEFORE encoding to JPEG
- Thread-safe with locks around `_latest_frame`
- JPEG encoding with quality setting from config

### Webhook System
- Queue-based with background worker thread
- Cooldown prevents spam (default 2 seconds between sends)
- Max queue size of 10 (drops oldest if full)
- Includes base64-encoded snapshot with each webhook
- **Priority-based filtering** (critical/high/normal/low/suppress)
  - Environmental motion: Automatically suppressed (no webhook)
  - Low confidence (<0.4): Automatically suppressed
  - Low priority: Suppressed unless enabled in settings
  - High/Critical: Always delivered
- Scene change alerts add ratio/mean/baseline-age metadata
- Motion alerts add classification/threat/speed/persistence metadata

### Scene Change Detection System
The camera monitors each servo position for unexpected changes in the view, independent of motion detection:

**How it works** (`application/services/scene_change_detector.py`):
1. **Per-Angle Baselines**: Divides the 180° pan/tilt range into buckets (default 5° each)
2. **First Visit**: When camera points to a position for the first time, captures baseline grayscale image
3. **Brightness-Normalized Comparison**:
   - Normalizes current frame to baseline brightness before comparing
   - Detects structural changes independent of lighting changes
   - Prevents false alerts from sunrise/sunset, clouds, shadows
4. **Subsequent Visits**: Compares current frame to stored baseline using:
   - Pixel-level difference threshold (default 25/255)
   - Minimum change ratio (default 3% of pixels must change)
   - Mean difference threshold (default 6% average difference)
   - **NEW**: Structural change verification (not just brightness shift)
5. **Adaptive Baseline Blending**:
   - No change detected: blend current frame into baseline (rolling average)
   - Lighting change detected: 3x faster blending (60% vs 20%) for quick adaptation
   - Significant structural change: queue webhook, then replace baseline after alert
6. **Cooldown**: Per-position cooldown (default 10s) prevents spam

**Integration** (`application/services/monitoring_service.py:130-135, 284-326`):
- Runs every frame when monitoring is active and servos are stable
- Independent from motion tracking (can detect scene changes without motion)
- Webhook payload includes `motion_detected=false` + scene change metadata
- Baselines reset when monitoring starts to handle lighting changes

**Use Cases**:
- Detect someone moving objects in view (e.g., furniture rearranged)
- Alert when door/window opens (background changes)
- Catch scene tampering (camera view blocked, redirected)
- Monitor for environmental changes (tree fallen, vehicle parked)

**Configuration** (`config/settings.py:49-65`):
- `SCENE_BUCKET_DEGREES`: Angle grouping precision (smaller = more positions)
- `SCENE_DIFF_PIXEL_THRESHOLD`: Pixel sensitivity (0-255, lower = more sensitive)
- `SCENE_DIFF_MIN_RATIO`: Fraction of pixels that must differ (0.0-1.0)
- `SCENE_DIFF_MEAN_THRESHOLD`: Average difference required (0.0-1.0)
- `SCENE_BASELINE_BLEND`: Rolling baseline smoothing (0.0=no update, 1.0=replace)
- `SCENE_CHANGE_COOLDOWN`: Seconds between alerts for same position

**Patrol Configuration** (`config/settings.py:57-66`):
- `PATROL_ENABLED`: Enable/disable autonomous patrol (default: true)
- `PATROL_DWELL_TIME`: Time to monitor each position (default: 3.0s)
- `PATROL_PAN_MIN/MAX/STEP`: Pan range and step (default: 30°-150° in 30° steps = 5 positions)
- `PATROL_TILT_MIN/MAX/STEP`: Tilt range and step (default: 150°-180° in 15° steps = 3 positions)
- `PATROL_SPEED_DPS`: Movement speed (default: 45°/s)
- Creates **pan×tilt grid**: Default 5×3 = **15 total positions**

**NOTE**: Motion tracking is completely disabled. The camera ONLY moves during patrol through the 2D grid, not when detecting motion.

**Webhook Payload Examples**:

Scene change (structural, not lighting):
```json
{
  "motion_detected": false,
  "priority": "normal",
  "scene_change_ratio": 0.1842,
  "scene_change_mean": 0.1125,
  "scene_baseline_age": 42.3,
  "scene_position_key": "pan~90.0°/tilt~170.0°",
  "pan_angle": 90.0,
  "tilt_angle": 170.0,
  "image_base64": "<snapshot>"
}
```

Motion detection (person):
```json
{
  "motion_detected": true,
  "priority": "high",
  "motion_classification": "person",
  "motion_threat_level": 0.735,
  "motion_confidence": 0.850,
  "motion_speed": 23.5,
  "motion_persistence": 0.7,
  "frame_brightness": 142.3,
  "pan_angle": 90.0,
  "tilt_angle": 165.0,
  "image_base64": "<snapshot>"
}
```

## Adding New Features

### Adding a New Repository (e.g., Cloud Storage)

1. **Define interface** in `domain/repositories/__init__.py`:
```python
class ICloudStorage(ABC):
    @abstractmethod
    def upload(self, frame: Frame) -> bool:
        pass
```

2. **Implement** in `infrastructure/cloud/`:
```python
class S3CloudStorage(ICloudStorage):
    def upload(self, frame: Frame) -> bool:
        # Implementation
```

3. **Inject** into MonitoringService (`main.py`):
```python
cloud_storage = S3CloudStorage()
monitoring_service = MonitoringService(
    camera_repo, servo_repo, motion_detector, webhook_repo, cloud_storage
)
```

4. **Use** in application layer (no changes to domain)

### Adding a New Value Object

Must be immutable (`@dataclass(frozen=True)`), contain validation in `__post_init__`, and live in `domain/value_objects/`.

### Adding a New Entity

Has identity, mutable state, and lifecycle. Lives in `domain/entities/`. Must not depend on infrastructure.

## Web UI Structure

**D-Pad Control** (presentation/templates/index.html:453-463):
- Uses CSS Grid with named areas for layout
- JavaScript `moveDpad()` function applies button step size
- Updates sliders in sync with button presses

**Configuration Panel** (lines 497-542):
- Grouped by category (Camera, Motion, Control, Webhook)
- `loadConfiguration()` fetches from `/config` GET on page load
- `saveConfiguration()` POSTs to `/config` endpoint
- Settings persist in `settings.py` class but reset on restart unless environment variables set

## Important Files

- `main.py`: Application entry point, dependency injection setup, signal handlers
- `config/settings.py`: All configuration with env var overrides
- `application/services/monitoring_service.py`: Core business logic orchestration
- `application/services/motion_intelligence.py`: Intelligent motion analysis with classification and threat assessment
- `application/services/scene_change_detector.py`: Scene baseline storage with brightness normalization
- `domain/`: Pure domain logic, no external dependencies
- `infrastructure/camera/picamera_repository.py`: Primary camera implementation
- `infrastructure/camera/motion_detector.py`: OpenCV motion detection with shape analysis
- `presentation/api/routes.py`: All Flask REST endpoints
- `INTELLIGENT_MOTION_DETECTION.md`: Documentation of intelligent motion features
- `FALSE_ALERT_REDUCTION.md`: Documentation of false alert reduction enhancements


## Common Pitfalls

1. **Don't import infrastructure in domain layer**: Domain must remain pure
2. **Don't bypass repository interfaces**: Always use abstractions, not concrete implementations
3. **Don't mutate value objects**: They're frozen for a reason (immutability guarantees)
4. **Don't add business logic to presentation layer**: Belongs in application/services
5. **Don't forget flip transforms**: Camera implementations must apply `CAMERA_FLIP_*` settings
6. **Don't send all motion as webhooks**: Use priority-based filtering to reduce false alerts
7. **Don't ignore lighting changes**: Scene detector now handles brightness normalization automatically

## Performance Considerations

Optimized for Raspberry Pi's limited resources:
- Single frame buffer (no buffering overhead)
- Background capture threads prevent blocking
- JPEG encoding with quality/performance tradeoff
- Minimal motion history (300 events max)
- Frame rate defaults to 15fps (not 30fps) for Pi 3A+
- Intelligent motion analysis adds ~1ms per frame (7% CPU overhead)
- Brightness normalization adds ~0.8ms per scene comparison
- Total intelligence overhead: ~4.5KB RAM, <10% CPU
- Heuristic-based classification (no ML models) for speed

## Testing Hardware Without Devices

Use mock repositories:
```python
from infrastructure.servo import MockServoRepository
servo_repo = MockServoRepository()  # No I2C required
```

## Extension Points

The architecture is designed for easy extension:
- Add new camera implementations (e.g., USB cameras, IP cameras)
- Add object detection (implement `IObjectDetector` repository)
- Add video recording (implement `IVideoRecorder` repository)
- Add MQTT support (implement `IMQTTRepository` repository)
- Add multiple camera support (extend `Camera` entity)
- Replace heuristic classification with ML models (modify `MotionIntelligence`)
- Add time-of-day baseline learning (extend `SceneChangeDetector`)
- Implement zone-based sensitivity (add zones to `MonitoringSession`)

All extensions follow the same pattern: define interface in domain, implement in infrastructure, inject into application service.

## False Alert Reduction

The system includes intelligent filtering to reduce false alerts by 80-85%:

### Brightness-Normalized Scene Detection
- Lighting changes (sunrise/sunset, clouds) no longer trigger alerts
- Structural changes (person, object) still detected
- Adaptive baseline blending (3x faster during lighting shifts)

### Intelligent Motion Classification
- **Person**: Vertical aspect ratio, moderate speed/size
- **Vehicle**: Horizontal aspect ratio, high speed
- **Animal**: Compact shape, moderate speed
- **Environmental**: Oscillating motion (trees), slow movement, large area
- **Suppressed**: Insects, low confidence, environmental motion

### Priority-Based Webhook Filtering
- **Critical**: High threat + high confidence → Always sent
- **High**: Significant threat or requires immediate attention → Always sent
- **Normal**: Moderate threat and significant motion → Always sent
- **Low**: Minor motion, unknown classification → Optional (default: suppressed)
- **Suppress**: Environmental motion, very low confidence → Never sent

### Oscillating Motion Detection
- Detects back-and-forth movement patterns (trees swaying in wind)
- Classifies as environmental, suppresses webhooks
- Reduces false alerts by ~50% in outdoor scenarios

**Configuration**:
```python
MOTION_INTELLIGENCE_ENABLED = True  # Enable intelligent analysis
WEBHOOK_SEND_LOW_PRIORITY = False  # Suppress low-priority alerts
WEBHOOK_SUPPRESS_ENVIRONMENTAL = True  # Never send environmental motion
```

See `FALSE_ALERT_REDUCTION.md` for comprehensive documentation.

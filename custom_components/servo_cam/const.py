"""Constants for the Servo Security Camera integration."""

DOMAIN = "servo_cam"
ZEROCONF_TYPE = "_servo-cam._tcp.local."

# Configuration
CONF_HOST = "host"
CONF_PORT = "port"

# Defaults
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 5000

# Update intervals
UPDATE_INTERVAL = 1  # seconds - frequent updates for camera status

# Preset positions
PRESET_POSITIONS = {
    "center": {"pan": 90.0, "tilt": 165.0},
    "left": {"pan": 30.0, "tilt": 165.0},
    "right": {"pan": 150.0, "tilt": 165.0},
    "up": {"pan": 90.0, "tilt": 150.0},
    "down": {"pan": 90.0, "tilt": 180.0},
    "top_left": {"pan": 30.0, "tilt": 150.0},
    "top_right": {"pan": 150.0, "tilt": 150.0},
    "bottom_left": {"pan": 30.0, "tilt": 180.0},
    "bottom_right": {"pan": 150.0, "tilt": 180.0},
}

# Event types
EVENT_MOTION_DETECTED = f"{DOMAIN}_motion_detected"
EVENT_SCENE_CHANGED = f"{DOMAIN}_scene_changed"
EVENT_HIGH_THREAT = f"{DOMAIN}_high_threat_detected"

# Attributes
ATTR_MOTION_CLASSIFICATION = "classification"
ATTR_MOTION_THREAT_LEVEL = "threat_level"
ATTR_MOTION_CONFIDENCE = "confidence"
ATTR_MOTION_SPEED = "speed"
ATTR_MOTION_PERSISTENCE = "persistence"
ATTR_SCENE_CHANGE_RATIO = "change_ratio"
ATTR_SCENE_CHANGE_MEAN = "mean_difference"
ATTR_SCENE_BASELINE_AGE = "baseline_age"
ATTR_PAN_ANGLE = "pan_angle"
ATTR_TILT_ANGLE = "tilt_angle"
ATTR_FRAME_BRIGHTNESS = "frame_brightness"

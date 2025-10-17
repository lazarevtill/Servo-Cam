#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration Management for Security Camera System
Centralized settings with environment variable support
"""
import os
from typing import Optional


class Settings:
    """Application settings with sensible defaults for Raspberry Pi"""

    # Camera Settings - Optimized for RPi 3A+ (512MB RAM)
    CAMERA_WIDTH: int = int(os.getenv("CAMERA_WIDTH", "640"))
    CAMERA_HEIGHT: int = int(os.getenv("CAMERA_HEIGHT", "480"))
    CAMERA_FPS: int = int(os.getenv("CAMERA_FPS", "15"))  # Reduced from 20 for lower CPU/RAM
    CAMERA_JPEG_QUALITY: int = int(os.getenv("CAMERA_JPEG_QUALITY", "75"))  # Reduced from 80
    CAMERA_FLIP_HORIZONTAL: bool = os.getenv("CAMERA_FLIP_H", "false").lower() == "true"
    CAMERA_FLIP_VERTICAL: bool = os.getenv("CAMERA_FLIP_V", "true").lower() == "true"  # Default to flip for upside-down mount
    CAMERA_ROTATION: int = int(os.getenv("CAMERA_ROTATION", "0"))  # 0, 90, 180, 270

    # Servo Settings
    SERVO_PAN_CHANNEL: int = 0
    SERVO_TILT_CHANNEL: int = 1
    SERVO_I2C_ADDRESS: int = 0x40
    SERVO_PWM_FREQUENCY: int = 50
    SERVO_MIN_MS: float = 1.0
    SERVO_MAX_MS: float = 2.0
    SERVO_ANGLE_RANGE: float = 180.0
    SERVO_CENTER_ANGLE: float = 90.0

    # Motion Detection Settings - Optimized for limited RAM
    MIN_AREA_RATIO: float = float(os.getenv("MIN_AREA_RATIO", "0.015"))
    MOTION_HISTORY_SIZE: int = 300  # Reduced from 500 to save memory
    MOTION_VAR_THRESHOLD: int = 40
    MOTION_BLUR_SIZE: int = 5
    MOTION_MORPHOLOGY_SIZE: int = 5

    # Intelligent Motion Analysis
    MOTION_INTELLIGENCE_ENABLED: bool = os.getenv("MOTION_INTELLIGENCE_ENABLED", "true").lower() == "true"
    MOTION_PERSISTENCE_WINDOW: int = int(os.getenv("MOTION_PERSISTENCE_WINDOW", "10"))  # Frames to track persistence
    MOTION_VALIDATION_FRAMES: int = int(os.getenv("MOTION_VALIDATION_FRAMES", "3"))  # Multi-frame validation
    MOTION_MIN_CONFIDENCE: float = float(os.getenv("MOTION_MIN_CONFIDENCE", "0.3"))  # Minimum confidence threshold
    MOTION_MIN_THREAT_ALERT: float = float(os.getenv("MOTION_MIN_THREAT_ALERT", "0.6"))  # Threat level for alerts

    # Webhook Filtering (False Alert Reduction)
    WEBHOOK_SEND_LOW_PRIORITY: bool = os.getenv("WEBHOOK_SEND_LOW_PRIORITY", "false").lower() == "true"  # Send low-priority alerts
    WEBHOOK_SUPPRESS_ENVIRONMENTAL: bool = os.getenv("WEBHOOK_SUPPRESS_ENVIRONMENTAL", "true").lower() == "true"  # Suppress environmental motion

    # Tracking Settings
    STABLE_FRAMES_REQUIRED: int = 3
    EMA_ALPHA: float = 0.25  # Exponential moving average smoothing
    DEADBAND_DEGREES: float = 2.0
    SERVO_MAX_SPEED_DPS: float = 90.0  # Degrees per second
    SERVO_UPDATE_INTERVAL: float = 0.05  # seconds
    RECENTER_IDLE_TIME: float = 4.0  # seconds
    RECENTER_SPEED_DPS: float = 40.0

    # Scene Change Monitoring
    SCENE_BUCKET_DEGREES: float = float(os.getenv("SCENE_BUCKET_DEGREES", "5.0"))
    SCENE_DIFF_PIXEL_THRESHOLD: int = int(os.getenv("SCENE_DIFF_PIXEL_THRESHOLD", "25"))
    SCENE_DIFF_MIN_RATIO: float = float(os.getenv("SCENE_DIFF_MIN_RATIO", "0.03"))
    SCENE_DIFF_MEAN_THRESHOLD: float = float(os.getenv("SCENE_DIFF_MEAN_THRESHOLD", "0.06"))
    SCENE_BASELINE_BLEND: float = float(os.getenv("SCENE_BASELINE_BLEND", "0.2"))
    SCENE_CHANGE_COOLDOWN: float = float(os.getenv("SCENE_CHANGE_COOLDOWN", "10.0"))

    # Patrol Mode (autonomous scene monitoring - NO motion tracking)
    PATROL_ENABLED: bool = os.getenv("PATROL_ENABLED", "true").lower() == "true"
    PATROL_DWELL_TIME: float = float(os.getenv("PATROL_DWELL_TIME", "3.0"))  # Time to spend at each position
    PATROL_PAN_MIN: float = float(os.getenv("PATROL_PAN_MIN", "30.0"))  # Minimum pan angle
    PATROL_PAN_MAX: float = float(os.getenv("PATROL_PAN_MAX", "150.0"))  # Maximum pan angle
    PATROL_PAN_STEP: float = float(os.getenv("PATROL_PAN_STEP", "30.0"))  # Degrees between pan positions
    PATROL_TILT_MIN: float = float(os.getenv("PATROL_TILT_MIN", "150.0"))  # Minimum tilt angle
    PATROL_TILT_MAX: float = float(os.getenv("PATROL_TILT_MAX", "180.0"))  # Maximum tilt angle
    PATROL_TILT_STEP: float = float(os.getenv("PATROL_TILT_STEP", "15.0"))  # Degrees between tilt positions
    PATROL_SPEED_DPS: float = float(os.getenv("PATROL_SPEED_DPS", "45.0"))  # Patrol movement speed

    # Manual Control Settings
    BUTTON_STEP_SIZE: float = float(os.getenv("BUTTON_STEP_SIZE", "10.0"))  # degrees per button press
    SERVO_SETTLING_TIME: float = 1.5  # seconds to wait after servo movement for camera to stabilize

    # Tilt angle constraints (to avoid looking at wrong objects)
    TILT_MIN_ANGLE: float = 150.0  # Don't look above this (avoid sails/ceiling)
    TILT_MAX_ANGLE: float = 180.0  # Max tilt angle

    # Motion visualization
    SHOW_MOTION_OVERLAY: bool = True  # Show motion detection rectangles/circles on feed

    # Webhook Settings
    WEBHOOK_URL: str = os.getenv(
        "WEBHOOK_URL",
        "https://n8n.lazarev.cloud/webhook/738f9e56-ab1f-4654-9f76-b018bc14d695"
    )
    WEBHOOK_ANGLE_THRESHOLD: float = float(os.getenv("WEBHOOK_ANGLE_THRESHOLD", "5.0"))
    WEBHOOK_COOLDOWN: float = float(os.getenv("WEBHOOK_COOLDOWN", "2.0"))
    WEBHOOK_TIMEOUT: float = 5.0
    WEBHOOK_QUEUE_MAX_SIZE: int = 10

    # Monitoring Mode Settings
    MONITORING_ENABLED_DEFAULT: bool = True

    # Flask Settings
    FLASK_HOST: str = os.getenv("FLASK_HOST", "0.0.0.0")
    FLASK_PORT: int = int(os.getenv("FLASK_PORT", "5000"))
    FLASK_DEBUG: bool = os.getenv("FLASK_DEBUG", "false").lower() == "true"

    # Performance Optimization Settings
    FRAME_BUFFER_SIZE: int = 1  # Keep only latest frame to save memory
    ENABLE_THREAD_PRIORITY: bool = True
    JPEG_ENCODE_THREADS: int = 2

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def validate(cls) -> bool:
        """Validate configuration settings"""
        try:
            assert 320 <= cls.CAMERA_WIDTH <= 1920, "Invalid camera width"
            assert 240 <= cls.CAMERA_HEIGHT <= 1080, "Invalid camera height"
            assert 1 <= cls.CAMERA_FPS <= 30, "Invalid FPS"
            assert 50 <= cls.CAMERA_JPEG_QUALITY <= 100, "Invalid JPEG quality"
            assert 0.0 < cls.MIN_AREA_RATIO < 1.0, "Invalid area ratio"
            assert cls.WEBHOOK_URL, "Webhook URL required"
            return True
        except AssertionError as e:
            print(f"Configuration error: {e}")
            return False

    @classmethod
    def print_config(cls):
        """Print current configuration"""
        print("\n" + "="*60)
        print("SECURITY CAMERA CONFIGURATION")
        print("="*60)
        print(f"Camera: {cls.CAMERA_WIDTH}x{cls.CAMERA_HEIGHT} @ {cls.CAMERA_FPS}fps")
        print(f"Motion Sensitivity: {cls.MIN_AREA_RATIO}")
        print(f"Webhook URL: {cls.WEBHOOK_URL}")
        print(f"Webhook Threshold: {cls.WEBHOOK_ANGLE_THRESHOLD}°")
        print(f"Webhook Cooldown: {cls.WEBHOOK_COOLDOWN}s")
        print(f"Server: {cls.FLASK_HOST}:{cls.FLASK_PORT}")
        print("="*60 + "\n")


# Global settings instance
settings = Settings()

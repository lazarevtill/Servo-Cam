#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Value Objects - Immutable domain concepts
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class Angle:
    """Immutable angle value object with validation"""
    degrees: float

    def __post_init__(self):
        if not 0.0 <= self.degrees <= 180.0:
            raise ValueError(f"Angle must be between 0-180°, got {self.degrees}")

    def __str__(self) -> str:
        return f"{self.degrees:.1f}°"

    def difference(self, other: 'Angle') -> float:
        """Calculate absolute difference between two angles"""
        return abs(self.degrees - other.degrees)


@dataclass(frozen=True)
class ServoPosition:
    """Immutable servo position with pan and tilt angles"""
    pan: Angle
    tilt: Angle
    timestamp: datetime

    @classmethod
    def centered(cls) -> 'ServoPosition':
        """Create centered position (90°, 90°)"""
        return cls(
            pan=Angle(90.0),
            tilt=Angle(90.0),
            timestamp=datetime.now()
        )

    def difference_from(self, other: 'ServoPosition') -> tuple[float, float]:
        """Calculate pan and tilt differences from another position"""
        return (
            self.pan.difference(other.pan),
            self.tilt.difference(other.tilt)
        )

    def max_difference_from(self, other: 'ServoPosition') -> float:
        """Get maximum difference (pan or tilt) from another position"""
        pan_diff, tilt_diff = self.difference_from(other)
        return max(pan_diff, tilt_diff)


@dataclass(frozen=True)
class MotionDetection:
    """
    Intelligent motion detection result with multi-dimensional analysis

    Attributes:
        detected: Whether motion was detected
        area: Motion blob area in pixels
        center_x/y: Centroid coordinates
        timestamp: Detection time
        confidence: Base detection confidence (0.0-1.0)
        bbox_*: Bounding box for visualization
        velocity_x/y: Estimated velocity in pixels/second (optional)
        aspect_ratio: Width/height ratio for shape classification
        compactness: Perimeter²/area ratio (circle=4π, indicates shape regularity)
        frame_brightness: Average brightness (0-255) for lighting context
        motion_persistence: How many consecutive frames motion present (0-1.0)
        classification: Motion type hint ('unknown', 'person', 'vehicle', 'animal', 'environmental')
        threat_level: Estimated threat score (0.0-1.0) based on multiple factors
    """
    detected: bool
    area: int
    center_x: int
    center_y: int
    timestamp: datetime
    confidence: float = 1.0
    # Bounding box for visualization (x, y, width, height)
    bbox_x: int = 0
    bbox_y: int = 0
    bbox_width: int = 0
    bbox_height: int = 0
    # Intelligent motion properties
    velocity_x: Optional[float] = None
    velocity_y: Optional[float] = None
    aspect_ratio: Optional[float] = None
    compactness: Optional[float] = None
    frame_brightness: Optional[float] = None
    motion_persistence: float = 0.0
    classification: str = "unknown"
    threat_level: float = 0.0

    @classmethod
    def no_motion(cls) -> 'MotionDetection':
        """Create no-motion result"""
        return cls(
            detected=False,
            area=0,
            center_x=0,
            center_y=0,
            timestamp=datetime.now(),
            confidence=0.0,
            bbox_x=0,
            bbox_y=0,
            bbox_width=0,
            bbox_height=0,
            velocity_x=0.0,
            velocity_y=0.0,
            motion_persistence=0.0,
            threat_level=0.0
        )

    @property
    def speed(self) -> float:
        """Calculate total speed magnitude (pixels/second)"""
        if self.velocity_x is None or self.velocity_y is None:
            return 0.0
        return (self.velocity_x**2 + self.velocity_y**2)**0.5

    @property
    def is_significant(self) -> bool:
        """
        Determine if motion is significant based on multi-factor analysis
        Combines confidence, persistence, and threat level
        """
        return (self.detected and
                self.confidence > 0.3 and
                self.motion_persistence > 0.2)

    @property
    def requires_immediate_attention(self) -> bool:
        """High-priority motion requiring immediate webhook notification"""
        return (self.detected and
                self.threat_level > 0.7 and
                self.confidence > 0.5)


@dataclass(frozen=True)
class Frame:
    """Camera frame wrapper"""
    data: bytes
    width: int
    height: int
    timestamp: datetime
    format: str = "JPEG"

    @property
    def size(self) -> int:
        """Get frame size in bytes"""
        return len(self.data)


@dataclass(frozen=True)
class WebhookPayload:
    """Intelligent webhook notification payload with threat assessment"""
    timestamp: datetime
    pan_angle: float
    tilt_angle: float
    previous_pan_angle: Optional[float]
    previous_tilt_angle: Optional[float]
    pan_change: float
    tilt_change: float
    motion_detected: bool
    image_base64: Optional[str]
    # Scene change detection
    scene_change_ratio: Optional[float] = None
    scene_change_mean: Optional[float] = None
    scene_baseline_age: Optional[float] = None
    scene_position_key: Optional[str] = None
    # Intelligent motion analysis
    motion_confidence: Optional[float] = None
    motion_classification: Optional[str] = None
    motion_threat_level: Optional[float] = None
    motion_speed: Optional[float] = None
    motion_persistence: Optional[float] = None
    frame_brightness: Optional[float] = None
    priority: str = "normal"  # "low", "normal", "high", "critical"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        payload = {
            "timestamp": self.timestamp.isoformat(),
            "date": self.timestamp.strftime("%Y-%m-%d"),
            "time": self.timestamp.strftime("%H:%M:%S"),
            "pan_angle": round(self.pan_angle, 1),
            "tilt_angle": round(self.tilt_angle, 1),
            "previous_pan_angle": round(self.previous_pan_angle, 1) if self.previous_pan_angle is not None else None,
            "previous_tilt_angle": round(self.previous_tilt_angle, 1) if self.previous_tilt_angle is not None else None,
            "pan_change": round(self.pan_change, 1),
            "tilt_change": round(self.tilt_change, 1),
            "motion_detected": self.motion_detected,
            "image_base64": self.image_base64,
            "priority": self.priority,
        }

        # Add scene change data if present
        if self.scene_change_ratio is not None:
            payload["scene_change_ratio"] = round(self.scene_change_ratio, 4)
        if self.scene_change_mean is not None:
            payload["scene_change_mean"] = round(self.scene_change_mean, 4)
        if self.scene_baseline_age is not None:
            payload["scene_baseline_age"] = round(self.scene_baseline_age, 1)
        if self.scene_position_key is not None:
            payload["scene_position_key"] = self.scene_position_key

        # Add intelligent motion data if present
        if self.motion_confidence is not None:
            payload["motion_confidence"] = round(self.motion_confidence, 3)
        if self.motion_classification is not None:
            payload["motion_classification"] = self.motion_classification
        if self.motion_threat_level is not None:
            payload["motion_threat_level"] = round(self.motion_threat_level, 3)
        if self.motion_speed is not None:
            payload["motion_speed"] = round(self.motion_speed, 2)
        if self.motion_persistence is not None:
            payload["motion_persistence"] = round(self.motion_persistence, 3)
        if self.frame_brightness is not None:
            payload["frame_brightness"] = round(self.frame_brightness, 1)

        return payload


__all__ = [
    'Angle',
    'ServoPosition',
    'MotionDetection',
    'Frame',
    'WebhookPayload'
]

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Domain Entities - Core business objects with identity
"""
from datetime import datetime
from typing import Optional, List
from collections import deque

from domain.value_objects import ServoPosition, MotionDetection, Frame


class Camera:
    """Camera entity representing the physical camera device"""

    def __init__(self, width: int, height: int, fps: int):
        self.width = width
        self.height = height
        self.fps = fps
        self.is_active = False
        self.last_frame: Optional[Frame] = None
        self.frame_count = 0

    def activate(self):
        """Activate the camera"""
        self.is_active = True

    def deactivate(self):
        """Deactivate the camera"""
        self.is_active = False

    def update_frame(self, frame: Frame):
        """Update the latest frame"""
        self.last_frame = frame
        self.frame_count += 1


class ServoController:
    """Servo controller entity managing pan/tilt servos"""

    def __init__(self, center_angle: float = 90.0):
        self.current_position = ServoPosition.centered()
        self.target_position: Optional[ServoPosition] = None
        self.is_connected = False
        self.center_angle = center_angle
        self._position_history: deque = deque(maxlen=10)

    def connect(self):
        """Mark controller as connected"""
        self.is_connected = True

    def disconnect(self):
        """Mark controller as disconnected"""
        self.is_connected = False

    def set_target(self, position: ServoPosition):
        """Set target position"""
        self.target_position = position

    def update_position(self, position: ServoPosition):
        """Update current position"""
        self._position_history.append(self.current_position)
        self.current_position = position

    def get_previous_position(self) -> Optional[ServoPosition]:
        """Get previous position for comparison"""
        return self._position_history[-1] if self._position_history else None

    def center(self) -> ServoPosition:
        """Get center position"""
        return ServoPosition.centered()


class MonitoringSession:
    """Monitoring session entity tracking security monitoring state"""

    _MOTION_HISTORY_LIMIT = 50

    def __init__(self, webhook_url: str, angle_threshold: float):
        self.id = datetime.now().timestamp()
        self.webhook_url = webhook_url
        self.angle_threshold = angle_threshold
        self.is_active = False
        self.started_at: Optional[datetime] = None
        self.stopped_at: Optional[datetime] = None
        self.motion_events: List[MotionDetection] = []
        self.webhook_sent_count = 0
        self.last_motion_at: Optional[datetime] = None

    def start(self):
        """Start monitoring session"""
        if not self.is_active:
            self.is_active = True
            self.started_at = datetime.now()

    def stop(self):
        """Stop monitoring session"""
        if self.is_active:
            self.is_active = False
            self.stopped_at = datetime.now()

    def record_motion(self, motion: MotionDetection):
        """Record a motion detection event"""
        if self.is_active:
            self.motion_events.append(motion)
            if len(self.motion_events) > self._MOTION_HISTORY_LIMIT:
                self.motion_events.pop(0)
            self.last_motion_at = motion.timestamp

    def record_webhook_sent(self):
        """Record that a webhook was sent"""
        self.webhook_sent_count += 1

    def get_statistics(self) -> dict:
        """Get session statistics"""
        duration = 0
        if self.started_at:
            end_time = self.stopped_at or datetime.now()
            duration = (end_time - self.started_at).total_seconds()

        now = datetime.now()
        recent_window = 60  # seconds
        recent_motions_raw = [
            motion for motion in self.motion_events
            if (now - motion.timestamp).total_seconds() < recent_window
        ]
        recent_motions = [self._serialize_motion(motion) for motion in recent_motions_raw]
        last_motion = self.motion_events[-1] if self.motion_events else None

        return {
            "session_id": self.id,
            "is_active": self.is_active,
            "duration_seconds": round(duration, 1),
            "session_duration": round(duration, 1),
            "total_motion_events": len(self.motion_events),
            "motion_count": len(self.motion_events),
            "recent_motion_events": len(recent_motions),
            "webhooks_sent": self.webhook_sent_count,
            "recent_motions": recent_motions,
            "motion_detected": bool(recent_motions_raw),
            "last_motion_timestamp": last_motion.timestamp.isoformat() if last_motion else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "stopped_at": self.stopped_at.isoformat() if self.stopped_at else None
        }

    @staticmethod
    def _serialize_motion(motion: MotionDetection) -> dict:
        """Convert MotionDetection to a serializable dictionary"""
        return {
            "timestamp": motion.timestamp.isoformat(),
            "confidence": round(motion.confidence, 3),
            "threat_level": round(motion.threat_level, 3),
            "classification": motion.classification,
            "speed": round(motion.speed, 2),
            "area": motion.area,
            "center_x": motion.center_x,
            "center_y": motion.center_y,
            "bbox": {
                "x": motion.bbox_x,
                "y": motion.bbox_y,
                "width": motion.bbox_width,
                "height": motion.bbox_height,
            },
        }


__all__ = [
    'Camera',
    'ServoController',
    'MonitoringSession'
]

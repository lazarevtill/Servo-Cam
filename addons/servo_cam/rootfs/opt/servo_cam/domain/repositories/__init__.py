#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Repository Interfaces - Abstract interfaces for infrastructure
"""
from abc import ABC, abstractmethod
from typing import Optional

from domain.value_objects import Frame, ServoPosition, MotionDetection, WebhookPayload


class ICameraRepository(ABC):
    """Interface for camera hardware access"""

    @abstractmethod
    def start(self) -> bool:
        """Start camera capture"""
        pass

    @abstractmethod
    def stop(self):
        """Stop camera capture"""
        pass

    @abstractmethod
    def capture_frame(self) -> Optional[Frame]:
        """Capture a single frame"""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if camera is available"""
        pass


class IServoRepository(ABC):
    """Interface for servo hardware control"""

    @abstractmethod
    def connect(self) -> bool:
        """Connect to servo controller"""
        pass

    @abstractmethod
    def disconnect(self):
        """Disconnect from servo controller"""
        pass

    @abstractmethod
    def move_to(self, position: ServoPosition) -> bool:
        """Move servos to specific position (immediate)"""
        pass

    @abstractmethod
    def move_towards(
        self,
        target: ServoPosition,
        max_speed_dps: float,
        deadband_degrees: float,
        min_interval: float
    ) -> tuple[bool, ServoPosition]:
        """
        Smooth movement towards target with speed limiting

        Returns: (moved: bool, new_position: ServoPosition)
        """
        pass

    @abstractmethod
    def get_current_position(self) -> ServoPosition:
        """Get current servo position"""
        pass

    @abstractmethod
    def get_previous_position(self) -> Optional[ServoPosition]:
        """Get previous servo position (for comparisons)"""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if controller is connected"""
        pass


class IMotionDetector(ABC):
    """Interface for motion detection"""

    @abstractmethod
    def detect(self, frame: Frame) -> MotionDetection:
        """Detect motion in frame"""
        pass

    @abstractmethod
    def reset(self):
        """Reset motion detection background model"""
        pass


class IWebhookRepository(ABC):
    """Interface for webhook notifications"""

    @abstractmethod
    def send(self, payload: WebhookPayload) -> bool:
        """Send webhook notification"""
        pass

    @abstractmethod
    def queue_send(self, payload: WebhookPayload):
        """Queue webhook for async sending"""
        pass

    @abstractmethod
    def get_queue_size(self) -> int:
        """Get number of queued webhooks"""
        pass


__all__ = [
    'ICameraRepository',
    'IServoRepository',
    'IMotionDetector',
    'IWebhookRepository'
]

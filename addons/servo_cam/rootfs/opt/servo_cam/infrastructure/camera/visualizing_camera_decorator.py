#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Visualizing Camera Decorator - Adds motion visualization overlays to frames
"""
from datetime import datetime
from typing import Optional
import cv2
import numpy as np

from config import settings
from domain.repositories import ICameraRepository
from domain.value_objects import Frame, MotionDetection


class VisualizingCameraDecorator(ICameraRepository):
    """
    Decorator that adds motion visualization to camera frames
    Draws bounding boxes and tracking circles on detected motion
    """

    def __init__(self, wrapped_camera: ICameraRepository):
        self.camera = wrapped_camera
        self.last_motion: Optional[MotionDetection] = None
        self.smoothed_x: Optional[float] = None
        self.smoothed_y: Optional[float] = None

    def start(self) -> bool:
        """Start the wrapped camera"""
        return self.camera.start()

    def stop(self):
        """Stop the wrapped camera"""
        self.camera.stop()

    def capture_frame(self) -> Optional[Frame]:
        """Capture frame and add motion visualization"""
        # Get original frame
        frame = self.camera.capture_frame()
        if not frame:
            return None

        # If visualization disabled, return original frame
        if not settings.SHOW_MOTION_OVERLAY:
            return frame

        # If no recent motion, return original frame
        if not self.last_motion or not self.last_motion.detected:
            return frame

        # Check if motion is recent (within 0.5 seconds)
        time_since_motion = (datetime.now() - self.last_motion.timestamp).total_seconds()
        if time_since_motion > 0.5:
            self.last_motion = None
            return frame

        try:
            # Decode JPEG to numpy array
            nparr = np.frombuffer(frame.data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if img is None:
                return frame

            # Draw bounding box (green rectangle)
            if self.last_motion.bbox_width > 0 and self.last_motion.bbox_height > 0:
                x = self.last_motion.bbox_x
                y = self.last_motion.bbox_y
                w = self.last_motion.bbox_width
                h = self.last_motion.bbox_height
                cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)

            # Draw smoothed center point (yellow circle) if available
            if self.smoothed_x is not None and self.smoothed_y is not None:
                cv2.circle(img, (int(self.smoothed_x), int(self.smoothed_y)), 5, (0, 255, 255), -1)

            # Re-encode to JPEG
            encode_param = [
                int(cv2.IMWRITE_JPEG_QUALITY),
                settings.CAMERA_JPEG_QUALITY,
                int(cv2.IMWRITE_JPEG_OPTIMIZE),
                1
            ]
            success, buffer = cv2.imencode('.jpg', img, encode_param)

            if success:
                return Frame(
                    data=buffer.tobytes(),
                    width=frame.width,
                    height=frame.height,
                    timestamp=datetime.now(),
                    format="JPEG"
                )

        except Exception as e:
            print(f"⚠ Visualization error: {e}")

        return frame

    def update_motion(self, motion: MotionDetection, smoothed_x: Optional[float] = None, smoothed_y: Optional[float] = None):
        """Update motion detection data for visualization"""
        self.last_motion = motion
        if smoothed_x is not None:
            self.smoothed_x = smoothed_x
        if smoothed_y is not None:
            self.smoothed_y = smoothed_y

    def is_available(self) -> bool:
        """Check if camera is available"""
        return self.camera.is_available()

    @property
    def is_active(self) -> bool:
        """Pass through is_active property from wrapped camera"""
        if hasattr(self.camera, 'is_active'):
            return self.camera.is_active
        return False

    @property
    def last_frame(self) -> Optional[Frame]:
        """Pass through last_frame property from wrapped camera"""
        if hasattr(self.camera, 'last_frame'):
            return self.camera.last_frame
        # Fallback to capture_frame for repositories that don't have last_frame
        return self.capture_frame()


__all__ = ['VisualizingCameraDecorator']

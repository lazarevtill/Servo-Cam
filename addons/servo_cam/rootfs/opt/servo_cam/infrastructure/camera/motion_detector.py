#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Motion Detection Implementation - Optimized for limited hardware
"""
from datetime import datetime
from typing import Optional

try:
    import cv2
    import numpy as np
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False

from config import settings
from domain.repositories import IMotionDetector
from domain.value_objects import MotionDetection, Frame


class OpenCVMotionDetector(IMotionDetector):
    """
    Optimized motion detector using OpenCV BackgroundSubtractorMOG2
    Memory-efficient for Raspberry Pi
    """

    def __init__(self):
        if not HAS_OPENCV:
            raise RuntimeError("OpenCV not available")

        # Background subtractor - optimized settings
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=settings.MOTION_HISTORY_SIZE,
            varThreshold=settings.MOTION_VAR_THRESHOLD,
            detectShadows=False  # Disable for performance
        )

        # Morphological kernel for noise reduction
        kernel_size = settings.MOTION_MORPHOLOGY_SIZE
        self.kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))

        # Minimum motion area
        self.min_area = int(
            settings.CAMERA_WIDTH * settings.CAMERA_HEIGHT * settings.MIN_AREA_RATIO
        )

    def detect(self, frame: Frame) -> MotionDetection:
        """
        Detect motion in frame
        Returns MotionDetection with largest contour
        """
        try:
            # Decode JPEG to numpy array
            nparr = np.frombuffer(frame.data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if img is None:
                return MotionDetection.no_motion()

            # Apply background subtraction
            fg_mask = self.bg_subtractor.apply(img)

            # Noise reduction with morphological operations
            fg_mask = cv2.medianBlur(fg_mask, settings.MOTION_BLUR_SIZE)
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, self.kernel, iterations=1)
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, self.kernel, iterations=1)

            # Find contours
            contours, _ = cv2.findContours(
                fg_mask,
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE
            )

            # Find largest contour
            best_contour = None
            best_area = self.min_area

            for contour in contours:
                area = cv2.contourArea(contour)
                if area > best_area:
                    best_area = area
                    best_contour = contour

            # If significant motion found
            if best_contour is not None:
                x, y, w, h = cv2.boundingRect(best_contour)
                center_x = x + w // 2
                center_y = y + h // 2

                # Confidence based on area ratio
                max_area = frame.width * frame.height
                confidence = min(1.0, best_area / (max_area * 0.5))

                # Calculate shape properties for intelligent analysis
                aspect_ratio = w / h if h > 0 else 1.0

                # Calculate compactness (perimeter²/area)
                perimeter = cv2.arcLength(best_contour, True)
                compactness = (perimeter ** 2) / best_area if best_area > 0 else 0.0
                # Normalize: circle = 4π ≈ 12.57
                compactness = min(1.0, compactness / 50.0)

                # Calculate frame brightness for context
                frame_brightness = float(np.mean(img))

                return MotionDetection(
                    detected=True,
                    area=int(best_area),
                    center_x=center_x,
                    center_y=center_y,
                    timestamp=datetime.now(),
                    confidence=confidence,
                    bbox_x=x,
                    bbox_y=y,
                    bbox_width=w,
                    bbox_height=h,
                    aspect_ratio=aspect_ratio,
                    compactness=compactness,
                    frame_brightness=frame_brightness
                )

        except Exception as e:
            print(f"⚠ Motion detection error: {e}")

        return MotionDetection.no_motion()

    def reset(self):
        """Reset background model"""
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=settings.MOTION_HISTORY_SIZE,
            varThreshold=settings.MOTION_VAR_THRESHOLD,
            detectShadows=False
        )


__all__ = ['OpenCVMotionDetector']

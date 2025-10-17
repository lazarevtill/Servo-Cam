#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Intelligent Motion Analysis Service
Provides multi-dimensional motion understanding for enhanced security monitoring
"""
from collections import deque
from datetime import datetime, timedelta
from typing import Optional, Deque, Tuple
from dataclasses import dataclass

from domain.value_objects import MotionDetection


@dataclass
class MotionTrajectory:
    """Represents motion path over time for prediction and analysis"""
    positions: Deque[Tuple[int, int, datetime]]  # (x, y, timestamp)
    max_history: int = 10

    def add_position(self, x: int, y: int, timestamp: datetime):
        """Add new position to trajectory"""
        self.positions.append((x, y, timestamp))
        if len(self.positions) > self.max_history:
            self.positions.popleft()

    def calculate_velocity(self) -> Tuple[float, float]:
        """
        Calculate average velocity in pixels/second
        Returns (velocity_x, velocity_y)
        """
        if len(self.positions) < 2:
            return (0.0, 0.0)

        # Use recent positions for velocity calculation
        recent = list(self.positions)[-3:]  # Last 3 positions
        if len(recent) < 2:
            return (0.0, 0.0)

        dx_total = 0.0
        dy_total = 0.0
        dt_total = 0.0

        for i in range(1, len(recent)):
            x1, y1, t1 = recent[i-1]
            x2, y2, t2 = recent[i]
            dt = (t2 - t1).total_seconds()
            if dt > 0:
                dx_total += (x2 - x1)
                dy_total += (y2 - y1)
                dt_total += dt

        if dt_total == 0:
            return (0.0, 0.0)

        return (dx_total / dt_total, dy_total / dt_total)

    def predict_position(self, seconds_ahead: float) -> Optional[Tuple[int, int]]:
        """Predict future position based on current trajectory"""
        if len(self.positions) < 2:
            return None

        vx, vy = self.calculate_velocity()
        last_x, last_y, _ = self.positions[-1]

        predicted_x = int(last_x + vx * seconds_ahead)
        predicted_y = int(last_y + vy * seconds_ahead)

        return (predicted_x, predicted_y)

    def clear(self):
        """Reset trajectory"""
        self.positions.clear()


class MotionIntelligence:
    """
    Intelligent motion analysis service providing:
    - Motion classification (person, vehicle, animal, environmental)
    - Threat level assessment
    - Adaptive sensitivity based on context
    - Multi-frame validation for false positive reduction
    - Trajectory tracking and prediction
    """

    def __init__(
        self,
        frame_width: int,
        frame_height: int,
        persistence_window: int = 10,
        validation_frames: int = 3
    ):
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.persistence_window = persistence_window
        self.validation_frames = validation_frames

        # Motion tracking state
        self._motion_history: Deque[MotionDetection] = deque(maxlen=persistence_window)
        self._trajectory = MotionTrajectory(positions=deque(), max_history=15)
        self._consecutive_detections = 0
        self._last_brightness: Optional[float] = None
        self._lighting_context: str = "unknown"  # "day", "night", "dusk", "dawn"

        # Adaptive thresholds
        self._min_confidence_threshold = 0.3
        self._min_persistence_threshold = 0.2

    def analyze(
        self,
        motion: MotionDetection,
        frame_brightness: float
    ) -> MotionDetection:
        """
        Enhance motion detection with intelligent analysis

        Args:
            motion: Base motion detection result
            frame_brightness: Average frame brightness (0-255)

        Returns:
            Enhanced MotionDetection with additional intelligence
        """
        # Update lighting context
        self._update_lighting_context(frame_brightness)

        if not motion.detected:
            self._consecutive_detections = 0
            self._trajectory.clear()
            self._motion_history.append(motion)
            return motion

        # Calculate motion persistence
        self._consecutive_detections += 1
        persistence = self._calculate_persistence()

        # Update trajectory and calculate velocity
        self._trajectory.add_position(
            motion.center_x,
            motion.center_y,
            motion.timestamp
        )
        velocity_x, velocity_y = self._trajectory.calculate_velocity()

        # Calculate enhanced properties
        aspect_ratio = self._calculate_aspect_ratio(motion)
        compactness = self._calculate_compactness(motion)

        # Classify motion type
        classification = self._classify_motion(
            motion,
            aspect_ratio,
            compactness,
            velocity_x,
            velocity_y
        )

        # Calculate threat level
        threat_level = self._calculate_threat_level(
            motion,
            classification,
            velocity_x,
            velocity_y,
            persistence
        )

        # Adjust confidence based on validation
        adjusted_confidence = self._validate_confidence(
            motion.confidence,
            persistence,
            frame_brightness
        )

        # Create enhanced motion detection
        enhanced = MotionDetection(
            detected=motion.detected,
            area=motion.area,
            center_x=motion.center_x,
            center_y=motion.center_y,
            timestamp=motion.timestamp,
            confidence=adjusted_confidence,
            bbox_x=motion.bbox_x,
            bbox_y=motion.bbox_y,
            bbox_width=motion.bbox_width,
            bbox_height=motion.bbox_height,
            velocity_x=velocity_x,
            velocity_y=velocity_y,
            aspect_ratio=aspect_ratio,
            compactness=compactness,
            frame_brightness=frame_brightness,
            motion_persistence=persistence,
            classification=classification,
            threat_level=threat_level
        )

        self._motion_history.append(enhanced)
        return enhanced

    def _calculate_persistence(self) -> float:
        """
        Calculate motion persistence score (0.0-1.0)
        Based on consecutive detection frames
        """
        return min(1.0, self._consecutive_detections / self.persistence_window)

    def _calculate_aspect_ratio(self, motion: MotionDetection) -> float:
        """Calculate bounding box aspect ratio (width/height)"""
        if motion.bbox_height == 0:
            return 1.0
        return motion.bbox_width / motion.bbox_height

    def _calculate_compactness(self, motion: MotionDetection) -> float:
        """
        Calculate shape compactness (perimeter²/area)
        Lower values indicate more compact/circular shapes
        Higher values indicate irregular or elongated shapes
        """
        if motion.area == 0:
            return 0.0

        # Approximate perimeter from bounding box
        perimeter = 2 * (motion.bbox_width + motion.bbox_height)
        compactness = (perimeter ** 2) / motion.area

        # Normalize (circle = 4π ≈ 12.57)
        return min(1.0, compactness / 50.0)  # Cap at 50 for normalization

    def _classify_motion(
        self,
        motion: MotionDetection,
        aspect_ratio: float,
        compactness: float,
        velocity_x: float,
        velocity_y: float
    ) -> str:
        """
        Classify motion type using heuristics

        Classifications:
        - person: Vertical aspect ratio (0.4-0.8), moderate speed
        - vehicle: Horizontal aspect ratio (>1.5), high speed, linear motion
        - animal: Small-medium size, erratic movement, moderate compactness
        - environmental: Large area, slow/no movement (trees, shadows)
        - insect: Very small, erratic, high speed relative to size
        """
        speed = (velocity_x**2 + velocity_y**2)**0.5
        area_ratio = motion.area / (self.frame_width * self.frame_height)

        # Insect/spider detection: very small near camera, erratic movement
        # These appear large in frame but have unusual movement patterns
        if area_ratio < 0.02 and speed > 30 and compactness > 0.6:
            return "environmental"  # Classify as environmental to reduce alerts

        # Vehicle detection: wide aspect ratio, high speed, linear path
        if aspect_ratio > 1.5 and speed > 50 and compactness < 0.5:
            return "vehicle"

        # Person detection: vertical aspect ratio, moderate speed/size
        # Tightened constraints to reduce false positives
        if 0.4 <= aspect_ratio <= 0.8 and 0.03 <= area_ratio <= 0.3 and 15 < speed < 100:
            return "person"

        # Animal detection: compact shape, moderate speed, medium size
        if compactness < 0.4 and 15 < speed < 80 and 0.02 < area_ratio < 0.15:
            return "animal"

        # Environmental (shadows, trees, rain): large area, slow movement, or oscillating
        if speed < 10 or area_ratio > 0.4 or self._is_oscillating_motion():
            return "environmental"

        return "unknown"

    def _calculate_threat_level(
        self,
        motion: MotionDetection,
        classification: str,
        velocity_x: float,
        velocity_y: float,
        persistence: float
    ) -> float:
        """
        Calculate threat level score (0.0-1.0)

        Factors:
        - Classification type (person/vehicle > animal > environmental)
        - Speed (faster = higher threat)
        - Direction (approaching = higher threat)
        - Persistence (sustained motion = higher threat)
        - Size (larger objects = higher threat)
        - Time of day (night = higher threat)
        """
        threat = 0.0

        # Base threat by classification
        classification_threats = {
            "person": 0.7,
            "vehicle": 0.6,
            "animal": 0.3,
            "environmental": 0.1,
            "unknown": 0.4
        }
        threat += classification_threats.get(classification, 0.4)

        # Speed factor (0-0.2)
        speed = (velocity_x**2 + velocity_y**2)**0.5
        speed_threat = min(0.2, speed / 200.0)
        threat += speed_threat

        # Persistence factor (0-0.15)
        threat += persistence * 0.15

        # Size factor (0-0.1)
        area_ratio = motion.area / (self.frame_width * self.frame_height)
        size_threat = min(0.1, area_ratio * 0.5)
        threat += size_threat

        # Lighting context modifier
        if self._lighting_context == "night":
            threat *= 1.3  # 30% increase at night
        elif self._lighting_context in ("dawn", "dusk"):
            threat *= 1.15  # 15% increase during twilight

        return min(1.0, threat)

    def _validate_confidence(
        self,
        base_confidence: float,
        persistence: float,
        frame_brightness: float
    ) -> float:
        """
        Adjust confidence based on multiple validation factors

        Reduces confidence for:
        - Low persistence (potential false positive)
        - Poor lighting conditions
        - Sudden changes in brightness (shadows, lighting flicker)
        """
        adjusted = base_confidence

        # Persistence bonus: sustained motion increases confidence
        if persistence > 0.5:
            adjusted *= (1.0 + persistence * 0.2)  # Up to 20% boost

        # Lighting penalty: low light reduces confidence
        if frame_brightness < 40:  # Very dark
            adjusted *= 0.7
        elif frame_brightness < 80:  # Low light
            adjusted *= 0.85

        # Brightness change penalty: sudden changes suggest shadows/artifacts
        if self._last_brightness is not None:
            brightness_change = abs(frame_brightness - self._last_brightness)
            if brightness_change > 30:  # Significant change
                adjusted *= 0.9

        self._last_brightness = frame_brightness

        return min(1.0, adjusted)

    def _update_lighting_context(self, brightness: float):
        """
        Determine lighting context based on frame brightness

        Ranges:
        - night: 0-50 (very dark)
        - dusk/dawn: 50-100 (twilight)
        - day: 100-255 (bright)
        """
        if brightness < 50:
            self._lighting_context = "night"
        elif brightness < 100:
            # Determine dawn vs dusk by checking if brightness is increasing
            if self._last_brightness is not None:
                if brightness > self._last_brightness:
                    self._lighting_context = "dawn"
                else:
                    self._lighting_context = "dusk"
            else:
                self._lighting_context = "dusk"
        else:
            self._lighting_context = "day"

    def get_predicted_position(self, seconds_ahead: float = 1.0) -> Optional[Tuple[int, int]]:
        """Get predicted position of tracked object"""
        return self._trajectory.predict_position(seconds_ahead)

    def get_lighting_context(self) -> str:
        """Get current lighting context"""
        return self._lighting_context

    def reset(self):
        """Reset analysis state"""
        self._motion_history.clear()
        self._trajectory.clear()
        self._consecutive_detections = 0
        self._last_brightness = None
        self._lighting_context = "unknown"

    def _is_oscillating_motion(self) -> bool:
        """
        Detect oscillating motion (like trees swaying) by analyzing trajectory.
        Returns True if motion is back-and-forth rather than directional.
        """
        if len(self._trajectory.positions) < 5:
            return False

        # Check if position changes direction frequently (oscillation)
        positions = list(self._trajectory.positions)
        direction_changes = 0

        for i in range(2, len(positions)):
            x1, y1, _ = positions[i-2]
            x2, y2, _ = positions[i-1]
            x3, y3, _ = positions[i]

            # Calculate direction vectors
            dx1 = x2 - x1
            dy1 = y2 - y1
            dx2 = x3 - x2
            dy2 = y3 - y2

            # Check if direction reversed (dot product negative)
            dot_product = dx1 * dx2 + dy1 * dy2
            if dot_product < 0:
                direction_changes += 1

        # If motion reverses direction frequently, it's oscillating
        oscillation_ratio = direction_changes / (len(positions) - 2)
        return oscillation_ratio > 0.6  # More than 60% of movements reverse direction


__all__ = ['MotionIntelligence', 'MotionTrajectory']

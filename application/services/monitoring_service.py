#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monitoring Service - Orchestrates security monitoring operations
"""
import base64
from datetime import datetime
from typing import Optional

from config import settings
from domain.entities import Camera, ServoController, MonitoringSession
from domain.value_objects import (
    Angle, ServoPosition, MotionDetection, Frame, WebhookPayload
)
from domain.repositories import (
    ICameraRepository, IServoRepository, IMotionDetector, IWebhookRepository
)

from .scene_change_detector import SceneChangeDetector
from .motion_intelligence import MotionIntelligence


class MonitoringService:
    """Service to manage security monitoring with intelligent motion tracking"""

    def __init__(
        self,
        camera_repo: ICameraRepository,
        servo_repo: IServoRepository,
        motion_detector: IMotionDetector,
        webhook_repo: IWebhookRepository
    ):
        self.camera_repo = camera_repo
        self.servo_repo = servo_repo
        self.motion_detector = motion_detector
        self.webhook_repo = webhook_repo

        # Domain entities
        self.camera = Camera(
            settings.CAMERA_WIDTH,
            settings.CAMERA_HEIGHT,
            settings.CAMERA_FPS
        )
        self.servo = ServoController(settings.SERVO_CENTER_ANGLE)
        self.session: Optional[MonitoringSession] = None

        # Intelligent motion analysis
        self._motion_intelligence = MotionIntelligence(
            frame_width=settings.CAMERA_WIDTH,
            frame_height=settings.CAMERA_HEIGHT,
            persistence_window=settings.MOTION_PERSISTENCE_WINDOW,
            validation_frames=settings.MOTION_VALIDATION_FRAMES
        )
        self._intelligence_enabled = settings.MOTION_INTELLIGENCE_ENABLED

        # Tracking state
        self._smoothed_x: Optional[float] = None
        self._smoothed_y: Optional[float] = None
        self._stable_frames = 0
        self._last_recenter_check = datetime.now()

        # Servo movement state (to prevent false motion detection)
        self._last_servo_movement_time: Optional[datetime] = None

        # Patrol state (stores tuples of (pan, tilt) positions)
        self._patrol_positions: list[tuple[float, float]] = []
        self._patrol_index: int = 0
        self._patrol_last_motion_time: datetime = datetime.now()
        self._patrol_position_start_time: Optional[datetime] = None
        self._is_patrolling: bool = False

        # Scene change tracking
        self._scene_detector = SceneChangeDetector(
            bucket_degrees=settings.SCENE_BUCKET_DEGREES,
            pixel_threshold=settings.SCENE_DIFF_PIXEL_THRESHOLD,
            min_change_ratio=settings.SCENE_DIFF_MIN_RATIO,
            mean_threshold=settings.SCENE_DIFF_MEAN_THRESHOLD,
            blend_factor=settings.SCENE_BASELINE_BLEND,
            cooldown=settings.SCENE_CHANGE_COOLDOWN,
        )

    def initialize(self) -> bool:
        """Initialize all hardware components"""
        success = True

        # Start camera
        if self.camera_repo.start():
            self.camera.activate()
            print("✓ Camera initialized")
        else:
            print("❌ Camera initialization failed")
            success = False

        # Connect servos
        if self.servo_repo.connect():
            self.servo.connect()
            # Center servos
            center_pos = self.servo.center()
            self.servo_repo.move_to(center_pos)
            self.servo.update_position(center_pos)
            print("✓ Servos initialized and centered")
        else:
            print("⚠ Servos not available")

        return success

    def start_monitoring(self) -> bool:
        """Start security monitoring session"""
        if self.session and self.session.is_active:
            return False

        self.session = MonitoringSession(
            webhook_url=settings.WEBHOOK_URL,
            angle_threshold=settings.WEBHOOK_ANGLE_THRESHOLD
        )
        self.session.start()
        if self._scene_detector.enabled:
            self._scene_detector.reset()

        # Initialize patrol positions
        if settings.PATROL_ENABLED:
            self._init_patrol_positions()
            self._patrol_last_motion_time = datetime.now()
            self._is_patrolling = False
            print(f"✓ Patrol mode enabled: {len(self._patrol_positions)} positions")

        print("✓ Monitoring started")
        return True

    def stop_monitoring(self) -> bool:
        """Stop security monitoring session"""
        if not self.session or not self.session.is_active:
            return False

        self.session.stop()
        print("✓ Monitoring stopped")
        return True

    def is_monitoring_active(self) -> bool:
        """Check if monitoring is active"""
        return self.session is not None and self.session.is_active

    def process_frame(self) -> Optional[Frame]:
        """
        Process one frame: capture, detect motion, track, send webhooks
        Returns the processed frame with overlays
        """
        # Capture frame
        frame = self.camera_repo.capture_frame()
        if not frame:
            return None

        self.camera.update_frame(frame)

        if (
            self.is_monitoring_active()
            and self.servo.is_connected
            and not self._is_servo_settling()
        ):
            self._analyze_scene_change(frame)

        # Only do motion detection and tracking if monitoring is active
        if self.is_monitoring_active():
            # Skip motion detection if servos are still settling
            if self._is_servo_settling():
                return frame

            # Detect motion
            base_motion = self.motion_detector.detect(frame)

            # Enhance with intelligent analysis if enabled
            if self._intelligence_enabled:
                motion = self._motion_intelligence.analyze(
                    base_motion,
                    base_motion.frame_brightness if base_motion.frame_brightness else 128.0
                )
            else:
                motion = base_motion

            if motion.detected:
                self.session.record_motion(motion)
                self._handle_motion_tracking(motion, frame)

            # Execute patrol regardless of motion (motion doesn't interrupt patrol)
            self._handle_patrol()

        return frame

    def _is_servo_settling(self) -> bool:
        """Check if servos are still settling after movement"""
        if self._last_servo_movement_time is None:
            return False

        time_since_movement = (datetime.now() - self._last_servo_movement_time).total_seconds()
        return time_since_movement < settings.SERVO_SETTLING_TIME

    def _handle_motion_tracking(self, motion: MotionDetection, frame: Frame):
        """Handle motion detection (NO servo movement, only logging)"""
        # Update camera visualization with motion data
        if hasattr(self.camera_repo, 'update_motion'):
            # Show motion for visualization only, don't move servos
            self.camera_repo.update_motion(motion, motion.center_x, motion.center_y)

        # NOTE: Motion tracking (servo movement) is DISABLED
        # Camera only moves during autonomous patrol
        # Motion is detected and logged but servos don't follow it

    def _handle_patrol(self):
        """Execute autonomous patrol (runs independently of motion)"""
        if not self.servo.is_connected:
            return

        # Execute patrol logic (runs continuously when monitoring is active)
        if settings.PATROL_ENABLED:
            now = datetime.now()

            if not self._is_patrolling:
                # Start patrol mode
                self._is_patrolling = True
                self._patrol_position_start_time = now
                print("→ Starting patrol mode")

            self._execute_patrol()

    def _track_target(self, frame: Frame):
        """Move servos to track motion target with smooth movement"""
        if not self._smoothed_x or not self._smoothed_y:
            return

        # Calculate target angles (inverted pan for natural tracking)
        pan_angle = 180.0 - (self._smoothed_x / self.camera.width) * 180.0
        tilt_angle = (self._smoothed_y / self.camera.height) * 180.0

        # Clamp pan to valid range (0-180)
        pan_angle = max(0.0, min(180.0, pan_angle))

        # Clamp tilt to constrained range (avoid looking at sails/ceiling)
        tilt_angle = max(settings.TILT_MIN_ANGLE, min(settings.TILT_MAX_ANGLE, tilt_angle))

        target = ServoPosition(
            pan=Angle(pan_angle),
            tilt=Angle(tilt_angle),
            timestamp=datetime.now()
        )

        # Use smooth movement towards target
        moved, new_position = self.servo_repo.move_towards(
            target,
            max_speed_dps=settings.SERVO_MAX_SPEED_DPS,
            deadband_degrees=settings.DEADBAND_DEGREES,
            min_interval=settings.SERVO_UPDATE_INTERVAL
        )

        if moved:
            # Mark servo movement time for settling period
            self._last_servo_movement_time = datetime.now()

            # Update servo entity with new position
            self.servo.update_position(new_position)

            # Get previous position for webhook comparison
            previous = self.servo_repo.get_previous_position()

            # Send webhook if change is significant
            if previous:
                self._maybe_send_webhook(new_position, previous, frame)

    def _maybe_send_webhook(
        self,
        current: ServoPosition,
        previous: ServoPosition,
        frame: Frame,
        motion: Optional[MotionDetection] = None
    ):
        """Send webhook if angle change exceeds threshold or motion requires attention"""
        pan_change, tilt_change = current.difference_from(previous)

        # Determine priority based on threat level and motion significance
        priority = self._calculate_webhook_priority(motion)

        # Don't send suppressed alerts
        if priority == "suppress":
            return

        # Determine if webhook should be sent
        should_send = (
            pan_change >= settings.WEBHOOK_ANGLE_THRESHOLD or
            tilt_change >= settings.WEBHOOK_ANGLE_THRESHOLD
        )

        # Override: immediate attention required
        if motion and motion.requires_immediate_attention:
            should_send = True

        # Apply priority-based filtering from settings
        if priority == "low" and not settings.WEBHOOK_SEND_LOW_PRIORITY:
            return

        if should_send:
            # Encode frame to base64
            image_b64 = base64.b64encode(frame.data).decode('utf-8')

            payload = WebhookPayload(
                timestamp=datetime.now(),
                pan_angle=current.pan.degrees,
                tilt_angle=current.tilt.degrees,
                previous_pan_angle=previous.pan.degrees,
                previous_tilt_angle=previous.tilt.degrees,
                pan_change=pan_change,
                tilt_change=tilt_change,
                motion_detected=True,
                image_base64=image_b64,
                motion_confidence=motion.confidence if motion else None,
                motion_classification=motion.classification if motion else None,
                motion_threat_level=motion.threat_level if motion else None,
                motion_speed=motion.speed if motion else None,
                motion_persistence=motion.motion_persistence if motion else None,
                frame_brightness=motion.frame_brightness if motion else None,
                priority=priority
            )

            self.webhook_repo.queue_send(payload)
            self.session.record_webhook_sent()

    def _calculate_webhook_priority(self, motion: Optional[MotionDetection]) -> str:
        """
        Calculate webhook priority based on threat assessment

        Returns: "low", "normal", "high", or "critical"
        """
        if not motion or not motion.detected:
            return "normal"

        threat = motion.threat_level
        confidence = motion.confidence
        classification = motion.classification

        # Suppress environmental motion completely (don't send webhook)
        if classification == "environmental":
            return "suppress"  # Special priority to skip webhook entirely

        # Critical: High threat + high confidence + requires immediate attention
        if threat >= 0.8 and confidence >= 0.7:
            return "critical"

        # High: Significant threat or immediate attention needed
        if threat >= 0.6 or motion.requires_immediate_attention:
            return "high"

        # Normal: Moderate threat or confirmed motion
        if threat >= 0.3 and motion.is_significant:
            return "normal"

        # Low: Minor motion, unknown classification, or moderate confidence
        # Still send these for analysis but mark as low priority
        if confidence >= 0.4:
            return "low"

        # Suppress very low confidence detections
        return "suppress"

    def _analyze_scene_change(self, frame: Frame) -> None:
        """Compare captured frame with stored baseline for the servo angle."""

        if not self._scene_detector.enabled:
            return

        position = self.servo.current_position
        result = self._scene_detector.evaluate(position, frame)
        if result is None or result.baseline_missing:
            return

        if not result.is_significant:
            return

        previous = self.servo.get_previous_position()
        pan_change = tilt_change = 0.0
        if previous:
            pan_change, tilt_change = position.difference_from(previous)

        image_b64 = base64.b64encode(frame.data).decode('utf-8')

        payload = WebhookPayload(
            timestamp=datetime.now(),
            pan_angle=position.pan.degrees,
            tilt_angle=position.tilt.degrees,
            previous_pan_angle=previous.pan.degrees if previous else None,
            previous_tilt_angle=previous.tilt.degrees if previous else None,
            pan_change=pan_change,
            tilt_change=tilt_change,
            motion_detected=False,
            image_base64=image_b64,
            scene_change_ratio=result.change_ratio,
            scene_change_mean=result.mean_difference,
            scene_baseline_age=result.baseline_age,
            scene_position_key=self._scene_detector.describe_bucket(result.bucket),
        )

        self.webhook_repo.queue_send(payload)

        if self.session and self.session.is_active:
            self.session.record_webhook_sent()

        self._scene_detector.commit_change(result.bucket)

    def manual_move(self, pan_angle: float, tilt_angle: float) -> bool:
        """Manually move servos to specific angles (no constraints for manual control)"""
        if not self.servo.is_connected:
            return False

        try:
            position = ServoPosition(
                pan=Angle(pan_angle),
                tilt=Angle(tilt_angle),
                timestamp=datetime.now()
            )

            if self.servo_repo.move_to(position):
                self._last_servo_movement_time = datetime.now()
                self.servo.update_position(position)
                return True
        except ValueError:
            pass

        return False

    def get_status(self) -> dict:
        """Get current system status"""
        stats = self.session.get_statistics() if self.session else {}

        return {
            "camera_active": self.camera.is_active,
            "servo_connected": self.servo.is_connected,
            "monitoring_active": self.is_monitoring_active(),
            "current_pan": round(self.servo.current_position.pan.degrees, 1),
            "current_tilt": round(self.servo.current_position.tilt.degrees, 1),
            "frame_count": self.camera.frame_count,
            "webhook_queue_size": self.webhook_repo.get_queue_size(),
            **stats
        }

    def shutdown(self):
        """Shutdown all components"""
        if self.is_monitoring_active():
            self.stop_monitoring()

        self.camera_repo.stop()
        self.camera.deactivate()

        if self.servo.is_connected:
            # Return to center before shutdown
            center = self.servo.center()
            self.servo_repo.move_to(center)
            self.servo_repo.disconnect()
            self.servo.disconnect()

        print("✓ System shutdown complete")

    def _init_patrol_positions(self):
        """Initialize patrol position grid (pan x tilt) based on configuration"""
        self._patrol_positions = []

        # Build pan angles
        pan_angles = []
        current_pan = settings.PATROL_PAN_MIN
        while current_pan <= settings.PATROL_PAN_MAX:
            pan_angles.append(current_pan)
            current_pan += settings.PATROL_PAN_STEP

        # Build tilt angles
        tilt_angles = []
        current_tilt = settings.PATROL_TILT_MIN
        while current_tilt <= settings.PATROL_TILT_MAX:
            tilt_angles.append(current_tilt)
            current_tilt += settings.PATROL_TILT_STEP

        # Create grid: for each tilt, sweep through all pans
        for tilt in tilt_angles:
            for pan in pan_angles:
                self._patrol_positions.append((pan, tilt))

        # Ensure we have at least one position
        if not self._patrol_positions:
            self._patrol_positions = [(90.0, 165.0)]  # Fallback to center

        self._patrol_index = 0
        print(f"  Grid: {len(pan_angles)} pan × {len(tilt_angles)} tilt = {len(self._patrol_positions)} positions")

    def _execute_patrol(self):
        """Execute patrol movement logic through pan/tilt grid"""
        if not self._patrol_positions:
            return

        now = datetime.now()

        # Check if we've dwelled long enough at current position
        if self._patrol_position_start_time:
            dwell_time = (now - self._patrol_position_start_time).total_seconds()
            if dwell_time < settings.PATROL_DWELL_TIME:
                return  # Still dwelling at current position

        # Get next patrol position (pan, tilt)
        target_pan, target_tilt = self._patrol_positions[self._patrol_index]

        target = ServoPosition(
            pan=Angle(target_pan),
            tilt=Angle(target_tilt),
            timestamp=now
        )

        # Move towards target position
        moved, new_position = self.servo_repo.move_towards(
            target,
            max_speed_dps=settings.PATROL_SPEED_DPS,
            deadband_degrees=settings.DEADBAND_DEGREES,
            min_interval=settings.SERVO_UPDATE_INTERVAL
        )

        if moved:
            self._last_servo_movement_time = now
            self.servo.update_position(new_position)

            # Check if we've reached the target
            pan_diff = abs(new_position.pan.degrees - target_pan)
            tilt_diff = abs(new_position.tilt.degrees - target_tilt)

            if pan_diff < settings.DEADBAND_DEGREES and tilt_diff < settings.DEADBAND_DEGREES:
                # Reached target - advance to next position
                self._patrol_index = (self._patrol_index + 1) % len(self._patrol_positions)
                self._patrol_position_start_time = now
                print(f"→ Patrol position {self._patrol_index + 1}/{len(self._patrol_positions)}: pan={target_pan}° tilt={target_tilt}°")


__all__ = ['MonitoringService']

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Picamera2 Repository - Optimized camera implementation for Raspberry Pi
"""
import threading
from datetime import datetime
from typing import Optional

try:
    from picamera2 import Picamera2
    import cv2
    import numpy as np
    HAS_PICAMERA2 = True
    HAS_OPENCV = True
except ImportError:
    HAS_PICAMERA2 = False
    HAS_OPENCV = False

from config import settings
from domain.repositories import ICameraRepository
from domain.value_objects import Frame


class PiCameraRepository(ICameraRepository):
    """
    Optimized Picamera2 implementation with background frame grabbing
    to minimize latency and CPU usage
    """

    def __init__(self):
        self.picam: Optional[Picamera2] = None
        self.width = settings.CAMERA_WIDTH
        self.height = settings.CAMERA_HEIGHT
        self.fps = settings.CAMERA_FPS

        self._lock = threading.Lock()
        self._latest_frame: Optional[Frame] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> bool:
        """Start camera capture in background thread"""
        if not HAS_PICAMERA2 or not HAS_OPENCV:
            print("❌ Picamera2 or OpenCV not available")
            return False

        with self._lock:
            if self._running:
                return True

            try:
                # Initialize Picamera2
                self.picam = Picamera2()

                # Configure for video with optimal settings
                config = self.picam.create_video_configuration(
                    main={"size": (self.width, self.height), "format": "RGB888"},
                    controls={
                        "FrameRate": self.fps,
                        # Optimize for low latency
                        "NoiseReductionMode": 0,  # Disable for speed
                    },
                    buffer_count=2  # Minimal buffering
                )

                self.picam.configure(config)
                self.picam.start()

                # Start background grabber thread
                self._running = True
                self._thread = threading.Thread(target=self._capture_loop, daemon=True)
                self._thread.start()

                print(f"✓ Picamera2 started: {self.width}x{self.height} @ {self.fps}fps")
                return True

            except Exception as e:
                print(f"❌ Picamera2 start failed: {e}")
                self.picam = None
                return False

    def stop(self):
        """Stop camera capture"""
        with self._lock:
            self._running = False

        if self._thread:
            self._thread.join(timeout=2.0)

        if self.picam:
            try:
                self.picam.stop()
                self.picam.close()
            except Exception:
                pass
            self.picam = None

        print("✓ Picamera2 stopped")

    def _capture_loop(self):
        """Background thread that continuously grabs frames"""
        while self._running:
            try:
                # Capture array from camera (RGB888)
                array = self.picam.capture_array("main")

                # Convert RGB to BGR for OpenCV compatibility
                bgr_frame = cv2.cvtColor(array, cv2.COLOR_RGB2BGR)

                # Apply flip/rotation transforms
                if settings.CAMERA_FLIP_HORIZONTAL:
                    bgr_frame = cv2.flip(bgr_frame, 1)
                if settings.CAMERA_FLIP_VERTICAL:
                    bgr_frame = cv2.flip(bgr_frame, 0)
                if settings.CAMERA_ROTATION == 90:
                    bgr_frame = cv2.rotate(bgr_frame, cv2.ROTATE_90_CLOCKWISE)
                elif settings.CAMERA_ROTATION == 180:
                    bgr_frame = cv2.rotate(bgr_frame, cv2.ROTATE_180)
                elif settings.CAMERA_ROTATION == 270:
                    bgr_frame = cv2.rotate(bgr_frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

                # Encode to JPEG with optimized quality
                encode_param = [
                    int(cv2.IMWRITE_JPEG_QUALITY),
                    settings.CAMERA_JPEG_QUALITY,
                    int(cv2.IMWRITE_JPEG_OPTIMIZE),
                    1
                ]
                success, buffer = cv2.imencode('.jpg', bgr_frame, encode_param)

                if success:
                    frame = Frame(
                        data=buffer.tobytes(),
                        width=self.width,
                        height=self.height,
                        timestamp=datetime.now(),
                        format="JPEG"
                    )

                    with self._lock:
                        self._latest_frame = frame

            except Exception as e:
                print(f"⚠ Frame capture error: {e}")
                # Brief pause before retry
                threading.Event().wait(0.1)

    def capture_frame(self) -> Optional[Frame]:
        """Get the latest captured frame"""
        with self._lock:
            return self._latest_frame

    def is_available(self) -> bool:
        """Check if camera is available"""
        return HAS_PICAMERA2 and HAS_OPENCV


class V4L2CameraRepository(ICameraRepository):
    """
    Fallback V4L2 camera implementation for when Picamera2 is unavailable
    """

    def __init__(self):
        self.cap: Optional[cv2.VideoCapture] = None
        self.width = settings.CAMERA_WIDTH
        self.height = settings.CAMERA_HEIGHT
        self.fps = settings.CAMERA_FPS

        self._lock = threading.Lock()
        self._latest_frame: Optional[Frame] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> bool:
        """Start V4L2 camera capture"""
        if not HAS_OPENCV:
            return False

        with self._lock:
            if self._running:
                return True

            try:
                self.cap = cv2.VideoCapture("/dev/video0", cv2.CAP_V4L2)
                if not self.cap.isOpened():
                    print("❌ V4L2: Failed to open /dev/video0")
                    return False

                # Try YUYV first (faster), then MJPEG
                success = False
                for fourcc in ['YUYV', 'MJPG']:
                    self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc))
                    self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                    self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                    self.cap.set(cv2.CAP_PROP_FPS, self.fps)
                    self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimal buffering

                    # Flush a few frames and test capture
                    for _ in range(3):
                        self.cap.grab()

                    ret, test_frame = self.cap.read()
                    if ret and test_frame is not None:
                        print(f"✓ V4L2 camera started: {fourcc} @ {self.width}x{self.height}")
                        success = True
                        break

                if not success:
                    print("❌ V4L2: Could not capture frames with YUYV or MJPG")
                    self.cap.release()
                    return False

                # Start capture thread
                self._running = True
                self._thread = threading.Thread(target=self._capture_loop, daemon=True)
                self._thread.start()

                return True

            except Exception as e:
                print(f"❌ V4L2 start failed: {e}")
                if self.cap:
                    self.cap.release()
                    self.cap = None
                return False

    def stop(self):
        """Stop camera"""
        with self._lock:
            self._running = False

        if self._thread:
            self._thread.join(timeout=2.0)

        if self.cap:
            self.cap.release()
            self.cap = None

    def _capture_loop(self):
        """Background capture loop"""
        while self._running:
            try:
                ret, bgr_frame = self.cap.read()
                if not ret or bgr_frame is None:
                    threading.Event().wait(0.01)
                    continue

                # Apply flip/rotation transforms
                if settings.CAMERA_FLIP_HORIZONTAL:
                    bgr_frame = cv2.flip(bgr_frame, 1)
                if settings.CAMERA_FLIP_VERTICAL:
                    bgr_frame = cv2.flip(bgr_frame, 0)
                if settings.CAMERA_ROTATION == 90:
                    bgr_frame = cv2.rotate(bgr_frame, cv2.ROTATE_90_CLOCKWISE)
                elif settings.CAMERA_ROTATION == 180:
                    bgr_frame = cv2.rotate(bgr_frame, cv2.ROTATE_180)
                elif settings.CAMERA_ROTATION == 270:
                    bgr_frame = cv2.rotate(bgr_frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

                # Encode to JPEG
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), settings.CAMERA_JPEG_QUALITY]
                success, buffer = cv2.imencode('.jpg', bgr_frame, encode_param)

                if success:
                    frame = Frame(
                        data=buffer.tobytes(),
                        width=self.width,
                        height=self.height,
                        timestamp=datetime.now(),
                        format="JPEG"
                    )

                    with self._lock:
                        self._latest_frame = frame

            except Exception:
                threading.Event().wait(0.1)

    def capture_frame(self) -> Optional[Frame]:
        """Get latest frame"""
        with self._lock:
            return self._latest_frame

    def is_available(self) -> bool:
        """Check if V4L2 is available"""
        return HAS_OPENCV


__all__ = ['PiCameraRepository', 'V4L2CameraRepository']

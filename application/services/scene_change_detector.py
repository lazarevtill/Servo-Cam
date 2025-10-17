#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Scene change detection helpers."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

try:
    import cv2
    import numpy as np
    HAS_OPENCV = True
except ImportError:  # pragma: no cover - OpenCV optional at runtime
    HAS_OPENCV = False
    cv2 = None  # type: ignore
    np = None  # type: ignore

from domain.value_objects import Frame, ServoPosition


@dataclass(frozen=True)
class SceneChangeResult:
    """Result from a scene comparison."""

    bucket: Tuple[int, int]
    baseline_missing: bool
    is_significant: bool
    change_ratio: float
    mean_difference: float
    baseline_age: Optional[float]


class SceneChangeDetector:
    """Maintain per-angle baselines and detect significant differences."""

    def __init__(
        self,
        bucket_degrees: float,
        pixel_threshold: int,
        min_change_ratio: float,
        mean_threshold: float,
        blend_factor: float,
        cooldown: float,
    ) -> None:
        self._enabled = HAS_OPENCV
        self.bucket_degrees = max(0.5, bucket_degrees)
        self.pixel_threshold = max(1, min(255, int(pixel_threshold)))
        self.min_change_ratio = max(0.0, min(1.0, float(min_change_ratio)))
        self.mean_threshold = max(0.0, min(1.0, float(mean_threshold)))
        self.blend_factor = max(0.0, min(1.0, float(blend_factor)))
        self.cooldown = max(0.0, float(cooldown))

        self._baselines: Dict[Tuple[int, int], "np.ndarray"] = {}
        self._baseline_timestamp: Dict[Tuple[int, int], float] = {}
        self._last_trigger_time: Dict[Tuple[int, int], float] = {}
        self._pending_updates: Dict[Tuple[int, int], "np.ndarray"] = {}

        # Track brightness per bucket to detect lighting changes vs. structural changes
        self._baseline_brightness: Dict[Tuple[int, int], float] = {}

        if not self._enabled:
            print("⚠ Scene change detection disabled (OpenCV not available)")

    @property
    def enabled(self) -> bool:
        """Whether detection is active."""

        return self._enabled

    def evaluate(self, position: ServoPosition, frame: Frame) -> Optional[SceneChangeResult]:
        """Compare current frame to stored baseline for the servo bucket."""

        if not self._enabled:
            return None

        grayscale = self._decode_to_gray(frame)
        if grayscale is None:
            return None

        bucket = self._bucket_position(position)
        baseline = self._baselines.get(bucket)
        now = time.time()

        if baseline is None:
            self._baselines[bucket] = grayscale
            self._baseline_timestamp[bucket] = now
            self._baseline_brightness[bucket] = float(np.mean(grayscale))
            return SceneChangeResult(
                bucket=bucket,
                baseline_missing=True,
                is_significant=False,
                change_ratio=0.0,
                mean_difference=0.0,
                baseline_age=None,
            )

        diff = cv2.absdiff(grayscale, baseline)
        mean_diff = float(np.mean(diff) / 255.0)
        change_ratio = float(np.count_nonzero(diff > self.pixel_threshold) / diff.size)
        baseline_age = now - self._baseline_timestamp.get(bucket, now)
        cooldown_ready = (now - self._last_trigger_time.get(bucket, 0.0)) >= self.cooldown

        # Detect if change is primarily due to lighting vs. structural change
        current_brightness = float(np.mean(grayscale))
        baseline_brightness = self._baseline_brightness.get(bucket, current_brightness)
        brightness_change = abs(current_brightness - baseline_brightness) / 255.0

        # Normalize difference by brightness to detect structural changes
        # If brightness changed significantly but pixel patterns are similar (just darker/lighter),
        # it's likely a lighting change, not a scene change
        brightness_normalized_diff = self._calculate_brightness_normalized_change(
            grayscale, baseline, current_brightness, baseline_brightness
        )

        # Use brightness-normalized difference for better filtering
        # If most change is just brightness (uniform), it's less significant
        is_structural_change = brightness_normalized_diff > (mean_diff * 0.7)

        is_significant = (
            change_ratio >= self.min_change_ratio
            and mean_diff >= self.mean_threshold
            and is_structural_change  # NEW: Must be structural, not just lighting
            and cooldown_ready
        )

        if is_significant:
            self._pending_updates[bucket] = grayscale
        else:
            # Adapt to gradual lighting changes but preserve structure
            # Use faster blending for lighting changes
            adaptive_blend = self.blend_factor
            if brightness_change > 0.1:  # Significant lighting change
                adaptive_blend = min(1.0, self.blend_factor * 3.0)  # Faster adaptation

            self._refresh_baseline(bucket, baseline, grayscale, now, adaptive_blend)
            self._baseline_brightness[bucket] = current_brightness

        return SceneChangeResult(
            bucket=bucket,
            baseline_missing=False,
            is_significant=is_significant,
            change_ratio=change_ratio,
            mean_difference=mean_diff,
            baseline_age=baseline_age,
        )

    def commit_change(self, bucket: Tuple[int, int]) -> None:
        """Persist the latest frame as new baseline after notifying."""

        if not self._enabled:
            return

        pending = self._pending_updates.pop(bucket, None)
        if pending is None:
            return

        now = time.time()
        self._baselines[bucket] = pending
        self._baseline_timestamp[bucket] = now
        self._last_trigger_time[bucket] = now
        self._baseline_brightness[bucket] = float(np.mean(pending))

    def describe_bucket(self, bucket: Tuple[int, int]) -> str:
        """Create a human readable description for a bucket."""

        pan_center = bucket[0] * self.bucket_degrees
        tilt_center = bucket[1] * self.bucket_degrees
        return f"pan~{pan_center:.1f}°/tilt~{tilt_center:.1f}°"

    def reset(self) -> None:
        """Clear stored baselines."""

        self._baselines.clear()
        self._baseline_timestamp.clear()
        self._last_trigger_time.clear()
        self._pending_updates.clear()
        self._baseline_brightness.clear()

    def _bucket_position(self, position: ServoPosition) -> Tuple[int, int]:
        return (
            int(round(position.pan.degrees / self.bucket_degrees)),
            int(round(position.tilt.degrees / self.bucket_degrees)),
        )

    def _decode_to_gray(self, frame: Frame) -> Optional["np.ndarray"]:
        if not self._enabled:
            return None

        try:
            nparr = np.frombuffer(frame.data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
        except Exception:
            return None

        if image is None:
            return None

        return image

    def _refresh_baseline(
        self,
        bucket: Tuple[int, int],
        baseline: "np.ndarray",
        current: "np.ndarray",
        timestamp: float,
        blend_factor: Optional[float] = None,
    ) -> None:
        """Refresh baseline with adaptive blending"""
        factor = blend_factor if blend_factor is not None else self.blend_factor

        if factor <= 0.0 or factor >= 1.0:
            blended = current
        else:
            blended = cv2.addWeighted(
                baseline.astype(np.float32),
                1.0 - factor,
                current.astype(np.float32),
                factor,
                0.0,
            ).astype(np.uint8)

        self._baselines[bucket] = blended
        self._baseline_timestamp[bucket] = timestamp

    def _calculate_brightness_normalized_change(
        self,
        current: "np.ndarray",
        baseline: "np.ndarray",
        current_brightness: float,
        baseline_brightness: float,
    ) -> float:
        """
        Calculate change that's independent of uniform brightness changes.
        Returns ratio of structural change (0.0-1.0)

        Strategy: Normalize both images to same brightness, then compare.
        If they're similar after normalization, change was just lighting.
        """
        if not self._enabled or current_brightness < 1.0 or baseline_brightness < 1.0:
            return 1.0  # Assume structural if too dark to normalize

        # Normalize current frame to baseline brightness
        brightness_ratio = baseline_brightness / current_brightness
        brightness_ratio = max(0.3, min(3.0, brightness_ratio))  # Clamp to reasonable range

        normalized_current = (current.astype(np.float32) * brightness_ratio).clip(0, 255).astype(np.uint8)

        # Compare normalized images
        norm_diff = cv2.absdiff(normalized_current, baseline)
        norm_mean_diff = float(np.mean(norm_diff) / 255.0)

        return norm_mean_diff


__all__ = ["SceneChangeDetector", "SceneChangeResult"]

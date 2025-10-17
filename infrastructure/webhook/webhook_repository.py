#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Webhook Repository - Async webhook notifications with queue
"""
import time
import threading
from collections import deque
from typing import Deque, Optional

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

from config import settings
from domain.repositories import IWebhookRepository
from domain.value_objects import WebhookPayload


class HTTPWebhookRepository(IWebhookRepository):
    """
    Webhook repository with async queue for non-blocking notifications
    Optimized for limited resources
    """

    def __init__(self, url: str = None, cooldown: float = None):
        self.url = url or settings.WEBHOOK_URL
        self.cooldown = cooldown or settings.WEBHOOK_COOLDOWN
        self.timeout = settings.WEBHOOK_TIMEOUT

        self._queue: Deque[WebhookPayload] = deque(maxlen=settings.WEBHOOK_QUEUE_MAX_SIZE)
        self._lock = threading.Lock()
        self._last_sent = 0.0

        self._running = False
        self._worker_thread: Optional[threading.Thread] = None

    def start_worker(self):
        """Start background worker thread"""
        if self._running:
            return

        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        print("✓ Webhook worker started")

    def stop_worker(self):
        """Stop background worker"""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=2.0)

    def _worker_loop(self):
        """Background worker that sends queued webhooks"""
        while self._running:
            payload_to_send = None

            with self._lock:
                # Check if we can send (cooldown period passed)
                if self._queue and time.time() - self._last_sent >= self.cooldown:
                    payload_to_send = self._queue.popleft()

            if payload_to_send:
                self._send_webhook(payload_to_send)
            else:
                # Sleep briefly to avoid busy-waiting
                time.sleep(0.1)

    def _send_webhook(self, payload: WebhookPayload) -> bool:
        """Actually send the webhook via HTTP POST"""
        if not HAS_REQUESTS:
            print("⚠ requests library not available")
            return False

        try:
            response = requests.post(
                self.url,
                json=payload.to_dict(),
                timeout=self.timeout,
                headers={'Content-Type': 'application/json'}
            )

            self._last_sent = time.time()

            if response.status_code == 200:
                print(f"✓ Webhook sent: Pan={payload.pan_angle:.1f}° Tilt={payload.tilt_angle:.1f}°")
                return True
            else:
                print(f"⚠ Webhook failed: HTTP {response.status_code}")
                return False

        except requests.exceptions.Timeout:
            print("⚠ Webhook timeout")
            return False
        except Exception as e:
            print(f"❌ Webhook error: {e}")
            return False

    def send(self, payload: WebhookPayload) -> bool:
        """Send webhook synchronously (blocking)"""
        return self._send_webhook(payload)

    def queue_send(self, payload: WebhookPayload):
        """Queue webhook for async sending (non-blocking)"""
        with self._lock:
            self._queue.append(payload)

            # Log if queue is getting full
            if len(self._queue) >= settings.WEBHOOK_QUEUE_MAX_SIZE * 0.8:
                print(f"⚠ Webhook queue filling up: {len(self._queue)}/{settings.WEBHOOK_QUEUE_MAX_SIZE}")

    def get_queue_size(self) -> int:
        """Get current queue size"""
        with self._lock:
            return len(self._queue)


class MockWebhookRepository(IWebhookRepository):
    """Mock webhook for testing"""

    def __init__(self):
        self._queue = []
        self.sent_count = 0

    def start_worker(self):
        pass

    def stop_worker(self):
        pass

    def send(self, payload: WebhookPayload) -> bool:
        self.sent_count += 1
        print(f"✓ Mock webhook sent: Pan={payload.pan_angle:.1f}° Tilt={payload.tilt_angle:.1f}°")
        return True

    def queue_send(self, payload: WebhookPayload):
        self._queue.append(payload)

    def get_queue_size(self) -> int:
        return len(self._queue)


__all__ = ['HTTPWebhookRepository', 'MockWebhookRepository']

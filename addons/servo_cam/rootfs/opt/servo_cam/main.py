#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Security Camera System - Main Entry Point
Clean Architecture with DDD principles
"""
import sys
import signal
from flask import Flask

from config import settings
from application.services import MonitoringService
from infrastructure.camera import PiCameraRepository, V4L2CameraRepository, OpenCVMotionDetector
from infrastructure.camera.visualizing_camera_decorator import VisualizingCameraDecorator
from infrastructure.servo import PCA9685ServoRepository
from infrastructure.discovery import ServoCamZeroconf
from infrastructure.webhook import HTTPWebhookRepository
from presentation.api import create_routes


def create_app() -> Flask:
    """Application factory"""
    app = Flask(
        __name__,
        template_folder='presentation/templates',
        static_folder='presentation/static'
    )

    # Flask config
    app.config['SECRET_KEY'] = 'change-this-in-production'
    app.config['JSON_SORT_KEYS'] = False

    return app


def initialize_infrastructure():
    """
    Initialize all infrastructure components
    Returns: (camera_repo, servo_repo, motion_detector, webhook_repo)
    """
    # Camera - try Picamera2 first, fallback to V4L2
    camera_repo = None

    # Try Picamera2
    if PiCameraRepository().is_available():
        try:
            camera_repo = PiCameraRepository()
            if camera_repo.start():
                print("✓ Using Picamera2")
                camera_repo.stop()  # Stop for now, will restart in monitoring service
            else:
                camera_repo = None
        except Exception as e:
            print(f"⚠ Picamera2 failed: {e}")
            camera_repo = None

    # Fallback to V4L2
    if camera_repo is None:
        try:
            camera_repo = V4L2CameraRepository()
            if camera_repo.start():
                print("✓ Using V4L2 camera")
                camera_repo.stop()  # Stop for now, will restart in monitoring service
            else:
                camera_repo = None
        except Exception as e:
            print(f"⚠ V4L2 failed: {e}")
            camera_repo = None

    if camera_repo is None:
        print("❌ No camera available!")
        sys.exit(1)

    # Wrap camera with visualization decorator
    camera_repo = VisualizingCameraDecorator(camera_repo)
    print("✓ Motion visualization enabled")

    # Servo controller
    servo_repo = PCA9685ServoRepository()

    # Motion detector
    try:
        motion_detector = OpenCVMotionDetector()
        print("✓ Motion detector initialized")
    except RuntimeError as e:
        print(f"❌ Motion detector failed: {e}")
        sys.exit(1)

    # Webhook
    webhook_repo = HTTPWebhookRepository()
    webhook_repo.start_worker()
    print("✓ Webhook worker started")

    return camera_repo, servo_repo, motion_detector, webhook_repo


def main():
    """Main entry point"""
    print("\n" + "="*60)
    print("SECURITY CAMERA SYSTEM")
    print("="*60 + "\n")

    # Validate configuration
    if not settings.validate():
        print("❌ Configuration validation failed")
        sys.exit(1)

    settings.print_config()

    # Initialize infrastructure
    camera_repo, servo_repo, motion_detector, webhook_repo = initialize_infrastructure()

    # Create application service
    monitoring_service = MonitoringService(
        camera_repo=camera_repo,
        servo_repo=servo_repo,
        motion_detector=motion_detector,
        webhook_repo=webhook_repo
    )

    # Initialize hardware
    if not monitoring_service.initialize():
        print("❌ Hardware initialization failed")
        sys.exit(1)

    # Start monitoring by default if configured
    if settings.MONITORING_ENABLED_DEFAULT:
        monitoring_service.start_monitoring()

    # Create Flask app
    app = create_app()

    # Register routes
    create_routes(app, monitoring_service)

    zeroconf_service: ServoCamZeroconf | None = None
    try:
        zeroconf_service = ServoCamZeroconf(settings.FLASK_HOST, settings.FLASK_PORT)
        zeroconf_service.start()
        print("✓ Zeroconf advertisement started")
    except Exception as exc:  # pylint: disable=broad-except
        print(f"⚠ Failed to start Zeroconf advertisement: {exc}")
        zeroconf_service = None

    # Graceful shutdown handler
    def signal_handler(sig, frame):
        print("\n\n⏹ Shutting down...")
        monitoring_service.shutdown()
        webhook_repo.stop_worker()
        if zeroconf_service is not None:
            zeroconf_service.stop()
        print("✓ Shutdown complete")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start server
    print("\n" + "="*60)
    print(f"🌐 Server starting on http://{settings.FLASK_HOST}:{settings.FLASK_PORT}")
    print("="*60 + "\n")
    print("Available endpoints:")
    print(f"  • Main UI:        http://{settings.FLASK_HOST}:{settings.FLASK_PORT}/")
    print(f"  • Video Feed:     http://{settings.FLASK_HOST}:{settings.FLASK_PORT}/video_feed")
    print(f"  • Snapshot:       http://{settings.FLASK_HOST}:{settings.FLASK_PORT}/snapshot")
    print(f"  • Status API:     http://{settings.FLASK_HOST}:{settings.FLASK_PORT}/status")
    print(f"  • Health Check:   http://{settings.FLASK_HOST}:{settings.FLASK_PORT}/healthz")
    print(f"  • Configuration:  http://{settings.FLASK_HOST}:{settings.FLASK_PORT}/config")
    print("\nPress Ctrl+C to stop\n")

    try:
        app.run(
            host=settings.FLASK_HOST,
            port=settings.FLASK_PORT,
            debug=settings.FLASK_DEBUG,
            threaded=True,
            use_reloader=False  # Disable reloader to avoid double initialization
        )
    except Exception as e:
        print(f"❌ Server error: {e}")
        monitoring_service.shutdown()
        webhook_repo.stop_worker()
        if zeroconf_service is not None:
            zeroconf_service.stop()
        sys.exit(1)
    finally:
        if zeroconf_service is not None:
            zeroconf_service.stop()


if __name__ == "__main__":
    main()

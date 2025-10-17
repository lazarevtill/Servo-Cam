#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask API Routes - RESTful endpoints for camera control
"""
import time
from flask import Flask, Response, jsonify, render_template, request, stream_with_context

from application.services import MonitoringService


def create_routes(app: Flask, monitoring_service: MonitoringService):
    """Register all Flask routes"""

    @app.route('/')
    def index():
        """Main web interface"""
        return render_template(
            'index.html',
            servo_connected=monitoring_service.servo.is_connected,
            monitoring_active=monitoring_service.is_monitoring_active()
        )

    @app.route('/video_feed')
    def video_feed():
        """MJPEG video stream"""
        def generate():
            # Send initial placeholder
            placeholder = create_placeholder_frame("Initializing camera...")
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + placeholder + b'\r\n')

            while True:
                try:
                    # Process frame
                    frame = monitoring_service.process_frame()

                    if frame:
                        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame.data + b'\r\n')
                    else:
                        # Send placeholder if no frame
                        placeholder = create_placeholder_frame("Waiting for camera...")
                        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + placeholder + b'\r\n')

                    time.sleep(0.033)  # ~30 FPS max

                except GeneratorExit:
                    break
                except Exception as e:
                    print(f"⚠ Stream error: {e}")
                    time.sleep(0.1)

        headers = {
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0"
        }

        return Response(
            stream_with_context(generate()),
            mimetype='multipart/x-mixed-replace; boundary=frame',
            headers=headers
        )

    @app.route('/snapshot')
    def snapshot():
        """Capture single snapshot"""
        frame = monitoring_service.camera.last_frame

        if frame:
            return Response(frame.data, mimetype='image/jpeg')
        else:
            placeholder = create_placeholder_frame("No frame available")
            return Response(placeholder, mimetype='image/jpeg')

    @app.route('/status')
    def status():
        """Get system status"""
        return jsonify(monitoring_service.get_status())

    @app.route('/healthz')
    def healthz():
        """Health check endpoint"""
        return jsonify({
            "status": "healthy",
            "camera_active": monitoring_service.camera.is_active,
            "servo_connected": monitoring_service.servo.is_connected,
            "monitoring_active": monitoring_service.is_monitoring_active()
        })

    @app.route('/monitoring/start', methods=['POST'])
    def start_monitoring():
        """Start security monitoring"""
        success = monitoring_service.start_monitoring()
        return jsonify({
            "status": "ok" if success else "already_running",
            "monitoring_active": monitoring_service.is_monitoring_active()
        }), 200 if success else 400

    @app.route('/monitoring/stop', methods=['POST'])
    def stop_monitoring():
        """Stop security monitoring"""
        success = monitoring_service.stop_monitoring()
        return jsonify({
            "status": "ok" if success else "not_running",
            "monitoring_active": monitoring_service.is_monitoring_active()
        }), 200 if success else 400

    @app.route('/monitoring/toggle', methods=['POST'])
    def toggle_monitoring():
        """Toggle monitoring on/off"""
        if monitoring_service.is_monitoring_active():
            monitoring_service.stop_monitoring()
        else:
            monitoring_service.start_monitoring()

        return jsonify({
            "status": "ok",
            "monitoring_active": monitoring_service.is_monitoring_active()
        })

    @app.route('/servo/move', methods=['POST'])
    def move_servo():
        """Manually move servos"""
        try:
            data = request.get_json(force=True)
            pan = float(data.get('pan', 90.0))
            tilt = float(data.get('tilt', 90.0))

            success = monitoring_service.manual_move(pan, tilt)

            return jsonify({
                "status": "ok" if success else "failed",
                "pan": pan,
                "tilt": tilt
            }), 200 if success else 500

        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @app.route('/servo/center', methods=['POST'])
    def center_servo():
        """Center servos"""
        success = monitoring_service.manual_move(90.0, 90.0)
        return jsonify({
            "status": "ok" if success else "failed"
        }), 200 if success else 500

    @app.route('/config', methods=['GET', 'POST'])
    def config():
        """Get or update configuration"""
        from config import settings

        if request.method == 'POST':
            try:
                data = request.get_json(force=True)

                # Update settings dynamically
                if 'motion_sensitivity' in data:
                    settings.MIN_AREA_RATIO = float(data['motion_sensitivity'])

                if 'webhook_angle_threshold' in data:
                    settings.WEBHOOK_ANGLE_THRESHOLD = float(data['webhook_angle_threshold'])

                if 'webhook_cooldown' in data:
                    settings.WEBHOOK_COOLDOWN = float(data['webhook_cooldown'])

                if 'button_step_size' in data:
                    settings.BUTTON_STEP_SIZE = float(data['button_step_size'])

                if 'flip_horizontal' in data:
                    settings.CAMERA_FLIP_HORIZONTAL = bool(data['flip_horizontal'])

                if 'flip_vertical' in data:
                    settings.CAMERA_FLIP_VERTICAL = bool(data['flip_vertical'])

                if 'show_motion_overlay' in data:
                    settings.SHOW_MOTION_OVERLAY = bool(data['show_motion_overlay'])

                if 'webhook_url' in data:
                    url = str(data['webhook_url']).strip()
                    if url:  # Only update if not empty
                        settings.WEBHOOK_URL = url

                # Patrol configuration
                if 'PATROL_ENABLED' in data:
                    settings.PATROL_ENABLED = bool(data['PATROL_ENABLED'])

                return jsonify({"status": "ok"}), 200

            except Exception as e:
                return jsonify({"error": str(e)}), 400
        else:
            # GET: Return current config
            return jsonify({
                "camera_width": settings.CAMERA_WIDTH,
                "camera_height": settings.CAMERA_HEIGHT,
                "camera_fps": settings.CAMERA_FPS,
                "flip_horizontal": settings.CAMERA_FLIP_HORIZONTAL,
                "flip_vertical": settings.CAMERA_FLIP_VERTICAL,
                "show_motion_overlay": settings.SHOW_MOTION_OVERLAY,
                "motion_sensitivity": settings.MIN_AREA_RATIO,
                "button_step_size": settings.BUTTON_STEP_SIZE,
                "webhook_url": settings.WEBHOOK_URL,
                "webhook_angle_threshold": settings.WEBHOOK_ANGLE_THRESHOLD,
                "webhook_cooldown": settings.WEBHOOK_COOLDOWN,
                "monitoring_enabled": monitoring_service.is_monitoring_active(),
                "patrol_enabled": settings.PATROL_ENABLED,
                "patrol_positions": len(monitoring_service._patrol_positions) if hasattr(monitoring_service, '_patrol_positions') else 0
            })


def create_placeholder_frame(message: str) -> bytes:
    """Create a placeholder frame with message"""
    try:
        import cv2
        import numpy as np

        img = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(
            img, message,
            (160, 240),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7, (255, 255, 255), 2
        )

        _, buffer = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        return buffer.tobytes()
    except:
        # Minimal black JPEG
        return (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\x09\x09\x08"
            b"\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d"
            b"\x1a\x1c\x1c $.'," b"\x1f\x20\x2c(\x30\x31\x2f(\x2b-7\x41\x37-39,,-\x00"
            b"\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x03\x01\"\x00\x02\x11\x01\x03\x11\x01"
            b"\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\xff\xc4\x00\x14\x10\x01\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xda\x00\x0c\x03\x01\x00\x02"
            b"\x11\x03\x11\x00?\x00\xff\xd9"
        )


__all__ = ['create_routes']

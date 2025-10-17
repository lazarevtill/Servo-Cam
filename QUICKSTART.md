# 🚀 Quick Start Guide

Get your security camera up and running in 5 minutes!

## Prerequisites

- Raspberry Pi (3B+ or newer) with Raspberry Pi OS
- Camera module connected
- PCA9685 servo controller wired
- Internet connection

## Step 1: Installation

```bash
cd /root/servo-cam-main
chmod +x install.sh
./install.sh
```

Wait for installation to complete (5-10 minutes). Reboot if prompted.

## Step 2: Configuration

Edit your webhook URL:

```bash
nano config/settings.py
```

Update line 63:
```python
WEBHOOK_URL = "https://your-webhook-url.com/endpoint"
```

Or use environment variable:
```bash
export WEBHOOK_URL="https://your-webhook-url.com/endpoint"
```

## Step 3: Test Run

```bash
source venv/bin/activate
python3 main.py
```

You should see:
```
============================================================
SECURITY CAMERA SYSTEM
============================================================

✓ Camera initialized
✓ Servos initialized and centered
✓ Webhook notifications enabled
...
🌐 Server starting on http://0.0.0.0:5000
```

## Step 4: Access Web Interface

Open your browser:
```
http://<raspberry-pi-ip>:5000
```

You should see:
- Live video feed
- Monitoring controls with toggle button
- Servo manual controls with arrow buttons

## Step 5: Enable Monitoring

Click the **"Start Monitoring"** button in the web interface.

The system will now:
- Detect motion in the camera view
- Track objects with servos
- Send webhooks when servos move significantly (>5°)
- Include snapshot with each webhook
- Compare the live scene with stored baselines for that angle and alert on unexpected changes

## Testing

### Test Servo Control

1. Use arrow buttons (◀ ◀◀ ▶ ▶▶) to move servos
2. Verify servos respond
3. Click "Center Servos" to return to center

### Test Monitoring

1. Click "Start Monitoring"
2. Badge should change to "🔴 MONITORING ACTIVE"
3. Move your hand in front of camera
4. Servos should track the movement
5. Check your webhook endpoint for notifications

## Troubleshooting

### No Video Feed

```bash
# Test camera
vcgencmd get_camera

# Check if picamera2 works
python3 -c "from picamera2 import Picamera2; print('Camera OK')"
```

### Servos Not Moving

```bash
# Check I2C devices
sudo i2cdetect -y 1
# Should show 0x40

# Test I2C communication
sudo i2cget -y 1 0x40 0x00
```

### Webhook Not Sending

1. Check webhook URL in config/settings.py
2. Verify internet connection
3. Check logs: `sudo journalctl -u security-cam -f`
4. Test webhook manually:
   ```bash
   curl -X POST https://your-webhook-url.com/endpoint \
        -H "Content-Type: application/json" \
        -d '{"test": true}'
   ```

## Enable Auto-Start

```bash
sudo systemctl enable security-cam
sudo systemctl start security-cam
```

Check status:
```bash
sudo systemctl status security-cam
```

## Key Features

### Monitoring Toggle
- **ON**: Motion tracking active, webhooks sent on servo movement
- **OFF**: Manual control only, no webhooks

### Manual Control
- Arrow buttons: Move servos in small/large steps
- Sliders: Precise angle control
- Center button: Return to 90°/90° position

### Webhook Triggers
Webhooks are sent when:
- Monitoring is active
- Motion is detected
- Servo angle changes by ≥5° (configurable)
- The scene at the current servo angle differs from the stored baseline beyond configured thresholds
- Includes base64-encoded snapshot

## Next Steps

- Adjust motion sensitivity in config/settings.py
- Change webhook angle threshold
- Set up systemd service for auto-start
- Integrate with Home Assistant, n8n, or other automation
- Add multiple cameras (extend architecture)

## Support

- Full docs: See README.md
- Logs: `sudo journalctl -u security-cam -f`
- Issues: Check hardware connections and permissions

---

**You're all set! Enjoy your security camera system! 🎉**

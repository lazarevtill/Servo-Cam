# 🚀 Quick Start Guide

Get your security camera up and running in 5 minutes!

## Prerequisites

- Raspberry Pi (3B+ or newer) with Raspberry Pi OS
- Camera module connected
- PCA9685 servo controller wired
- Internet connection

## Step 1: Installation

1. **Home Assistant Add-on (Recommended)**
   - Add repository: Settings → Add-ons → Add-on Store → ⋮ → Repositories → `https://github.com/lazarevtill/Servo-Cam`
   - Install & start the **Servo Cam** add-on (enable auto-start/watchdog if desired)

2. **Manual on-device install (for development/standalone)**

   ```bash
   cd /root/servo-cam-main
   sudo apt-get update
   sudo apt-get install -y python3 python3-pip python3-venv \
        i2c-tools libopencv-dev python3-opencv

   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

   Reboot after enabling I2C if prompted by `raspi-config`.

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
✓ Motion detector initialized
✓ Webhook worker started
✓ Zeroconf advertisement started
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
- Detect motion in the camera view (for overlays, intelligence, and webhook payloads)
- Continue autonomous patrol scanning across the configured pan/tilt grid (servos do **not** follow motion targets)
- Send webhooks when patrol movement exceeds the configured thresholds or when scene-change analysis flags a difference
- Include a base64 snapshot with each webhook
- Compare the live scene with stored baselines for that angle and alert on unexpected changes

> 💡 **Home Assistant**: Leave `python3 main.py` (manual install) or the add-on running. Home Assistant will show a "New device discovered" prompt thanks to the Zeroconf broadcast. Accept it to create the integration entry instantly.

## Testing

### Test Servo Control

1. Use arrow buttons (◀ ◀◀ ▶ ▶▶) to move servos
2. Verify servos respond
3. Click "Center Servos" to return to center

### Test Monitoring

1. Click "Start Monitoring"
2. Badge should change to "🔴 MONITORING ACTIVE"
3. Move your hand in front of camera
4. Watch the console or web UI overlay to confirm motion is detected (servos stay in patrol sequence)
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
- **ON**: Motion detection, intelligent analysis, autonomous patrol, scene-change monitoring, and webhooks are active
- **OFF**: Manual control only, no monitoring or webhooks

### Manual Control
- Arrow buttons: Move servos in small/large steps
- Sliders: Precise angle control
- Center button: Return to 90°/90° position

### Webhook Triggers
Webhooks are sent when:
- Monitoring is active
- Motion intelligence marks an event that meets the threat filters
- Patrol movement changes pan/tilt angles by ≥5° (configurable)
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

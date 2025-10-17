# 🚀 Quick Start Guide

Get your security camera up and running in 5 minutes!

## Prerequisites

- Raspberry Pi (3B+ or newer) with Raspberry Pi OS
- Camera module connected
- PCA9685 servo controller wired
- Internet connection

## Step 1: Installation

### Raspberry Pi Deployment (recommended)

```bash
cd ~/Servo-Cam
./install.sh --systemd --start   # Provision, install, register systemd, and start immediately
```

The helper installs apt + pip dependencies, creates `.venv`, copies the Home Assistant integration into your config directory (`~/.homeassistant` by default), and keeps the backend running. Logs are written to `logs/servo_cam.log`.

Need to target a different Home Assistant config? Use `HA_CONFIG_DIR=/path/to/config ./install.sh --systemd --start`.

### Manual fallback (if you cannot run the helper)

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv \
    i2c-tools libopencv-dev python3-opencv

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Home Assistant Add-on

1. Open **Settings → Add-ons → Add-on Store**
2. Click **⋮ → Repositories** and add `https://github.com/lazarevtill/Servo-Cam`
3. Install & start **Servo Cam** (enable auto-start/watchdog if desired)

> ⚠️ Hardware access is exclusive—run either the add-on or the standalone service, not both simultaneously.

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

## Step 3: Verify the Backend

If you used `--start`, the service is already running. Confirm with:

```bash
curl http://localhost:5000/healthz
tail -f logs/servo_cam.log
```

Manual launch remains available:

```bash
source .venv/bin/activate
python3 main.py
```

You should see the startup banner with camera/servo initialization, webhook worker startup, Zeroconf advertisement, and the Flask server binding to `http://0.0.0.0:5000`.

## Step 4: Access Web Interface

Open your browser to:

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

> 💡 **Home Assistant**: Leave the backend running. Home Assistant should raise a "New device discovered" prompt via Zeroconf. No discovery? Click **+ Add Integration**, search for **Servo Security Camera**, and enter the Raspberry Pi host/IP (default `servo-cam.local`) and port `5000` manually.

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

If you did not run `./install.sh --systemd`, you can still enable the service manually:

```bash
sudo systemctl enable security-cam
sudo systemctl start security-cam

# Check status
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

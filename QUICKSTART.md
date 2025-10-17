# 🚀 Quick Start Guide

Spin up the Servo Cam platform, expose it to Home Assistant, and verify everything in a few minutes.

## Prerequisites

- Raspberry Pi 3B+ (or newer) running Raspberry Pi OS
- Camera module (CSI or USB) connected and enabled
- PCA9685 servo controller wired to the servos
- Network access for Home Assistant and webhook targets

## Step 1: Install the Backend

1. **Home Assistant Add-on (Recommended)**
   - Go to **Settings → Add-ons → Add-on Store**
   - Click the **⋮** menu → **Repositories** → add `https://github.com/lazarevtill/Servo-Cam`
   - Install and start the **Servo Cam** add-on (optional: enable auto-start/watchdog)
   - *Default `mode: local` runs on Home Assistant OS/Supervised for Raspberry Pi (ARM). For x86 or other hosts, set the add-on option `mode: remote` and point it at the Raspberry Pi where you ran `install.sh`.*

   After installation, open the add-on configuration (gear icon) and:
   - Leave `mode: local` when Home Assistant runs on the same Raspberry Pi as the camera/servos.
   - Switch to `mode: remote` on x86/other platforms, then set `remote_host` (Pi IP/DNS) and `remote_port` (default 5000) before starting the add-on.

2. **On-device install (Raspberry Pi)**
   ```bash
   cd /home/pi/Servo-Cam               # adjust to your clone location
   chmod +x install.sh
   ./install.sh
   ```
   The installer:
   - Installs all apt dependencies (Picamera2, OpenCV, I²C tools, etc.)
   - Creates a Python virtual environment in `.venv`
   - Installs Python requirements
   - Writes `/etc/servo_cam/servo_cam.env` for runtime overrides
   - Registers and starts the `servo-cam.service` systemd unit

3. **Development-only workflow**
   ```bash
   sudo apt-get update
   sudo apt-get install -y python3 python3-venv python3-opencv i2c-tools
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
   Use this path only when you want to run `python3 main.py` manually from the shell.

## Step 2: Configure Runtime Settings

Edit the environment file created by the installer:

```bash
sudo nano /etc/servo_cam/servo_cam.env
```

Set overrides for your environment (example):

```env
WEBHOOK_URL=https://example.com/webhook
FLASK_PORT=5000
MOTION_INTELLIGENCE_ENABLED=true
PATROL_ENABLED=true
PATROL_DWELL_TIME=3.0
```

Reload the service when you are done:

```bash
sudo systemctl restart servo-cam.service
```

> Developing without systemd? Export the same variables in your shell before running `python3 main.py`.

## Step 3: Verify the Service

```bash
sudo systemctl status servo-cam.service
sudo journalctl -fu servo-cam.service
```

You should see the banner followed by:

```
✓ Camera initialized
✓ Servos initialized and centered
✓ Motion detector initialized
✓ Webhook worker started
✓ Zeroconf advertisement started
🌐 Server starting on http://0.0.0.0:5000
```

## Step 4: Open the Web UI

Visit `http://<raspberry-pi-ip>:5000` and confirm:
- Live MJPEG video feed
- Monitoring toggle (should show **Monitoring Active** after you start it)
- Servo manual controls and patrol status

## Step 5: Link with Home Assistant

- Keep the backend running (systemd service or manual session)
- In Home Assistant, go to **Settings → Devices & Services**
- Accept the **Servo Security Camera** Zeroconf prompt, or click **+ Add Integration** and search for it
- Confirm host/port and finish the flow

The integration will create:
- 1 camera entity (`camera.servo_security_camera`)
- 9 sensors (angles, counts, queue size, threat info)
- 5 binary sensors (monitoring, patrol, servo/camera connectivity, live motion)
- 2 switches (monitoring, patrol)
- 5 helper services (move_servo, preset_position, start/stop patrol, center_camera)

## Testing Checklist

### Servo Movement
1. From the web UI, use the arrow buttons or sliders
2. Confirm the servos move and return to center on command

### Monitoring & Alerts
1. Click **Start Monitoring**
2. Move in front of the camera
3. Watch the overlay for motion bounding boxes
4. Tail the logs or webhook endpoint to confirm notifications

### Home Assistant
1. Ensure the camera entity streams (`camera_view: live`)
2. Toggle `switch.servo_cam_monitoring` and see status update in the UI
3. Call `servo_cam.preset_position` → `top_left` and confirm servo motion

## Troubleshooting Quick Hits

| Issue | Resolution |
|-------|------------|
| No video feed | `vcgencmd get_camera`, ensure Picamera2/OpenCV packages installed |
| Servos idle | `sudo i2cdetect -y 1` (expect `0x40`), check wiring and power |
| Webhooks missing | Verify URL in `/etc/servo_cam/servo_cam.env`, check `journalctl -fu servo-cam.service`, test with `curl` |
| HA can't connect | Confirm `http://<pi-ip>:5000/healthz` returns JSON, firewall open |

## Service Controls

```bash
sudo systemctl stop servo-cam.service
sudo systemctl start servo-cam.service
sudo systemctl restart servo-cam.service
sudo journalctl -fu servo-cam.service
```

## Next Steps

- Fine-tune patrol dwell, detection sensitivity, and webhook thresholds via the environment file
- Build Home Assistant automations (examples in `HOMEASSISTANT_INTEGRATION.md` and `HA_QUICK_REFERENCE.md`)
- Point webhooks to n8n, Home Assistant automations, or other incident pipelines
- Explore the web UI to trigger snapshots, download logs, or deploy future features

You are up and running—enjoy your Servo Cam smart security platform! 🎉

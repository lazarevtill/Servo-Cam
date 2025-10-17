#!/bin/bash
# Installation script for Security Camera System
# Optimized for Raspberry Pi with limited resources

set -e

echo "========================================"
echo "Security Camera System - Installation"
echo "========================================"
echo ""

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo "⚠️  Warning: This script is optimized for Raspberry Pi"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Update system
echo "📦 Updating system packages..."
sudo apt-get update

# Install system dependencies
echo "📦 Installing system dependencies..."
sudo apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    i2c-tools \
    libopencv-dev \
    python3-opencv \
    libatlas-base-dev \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev

# Enable I2C
echo "🔧 Enabling I2C..."
if ! grep -q "^dtparam=i2c_arm=on" /boot/config.txt; then
    echo "dtparam=i2c_arm=on" | sudo tee -a /boot/config.txt
    echo "✓ I2C enabled (requires reboot)"
else
    echo "✓ I2C already enabled"
fi

# Enable camera
echo "🔧 Enabling camera..."
if ! grep -q "^start_x=1" /boot/config.txt; then
    echo "start_x=1" | sudo tee -a /boot/config.txt
    echo "gpu_mem=128" | sudo tee -a /boot/config.txt
    echo "✓ Camera enabled (requires reboot)"
else
    echo "✓ Camera already enabled"
fi

# Create virtual environment with system site-packages for libcamera access
echo "🐍 Creating Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv --system-site-packages venv
    echo "✓ Virtual environment created with system site-packages"
else
    echo "✓ Virtual environment already exists"
    echo "  To enable system packages: rm -rf venv && python3 -m venv --system-site-packages venv"
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Install Picamera2 if available
echo "📦 Installing Picamera2..."
if python3 -c "import picamera2" 2>/dev/null; then
    echo "✓ Picamera2 already installed"
else
    pip install picamera2 || echo "⚠️  Picamera2 installation failed (not critical)"
fi

# Check I2C devices
echo ""
echo "🔍 Checking I2C devices..."
if command -v i2cdetect &> /dev/null; then
    sudo i2cdetect -y 1 || echo "⚠️  No I2C devices detected"
else
    echo "⚠️  i2cdetect not available"
fi

# Create systemd service
echo ""
echo "🔧 Creating systemd service..."
sudo tee /etc/systemd/system/security-cam.service > /dev/null <<EOF
[Unit]
Description=Security Camera System
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/venv/bin/python3 $(pwd)/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "✓ Systemd service created"

# Set permissions
echo "🔒 Setting permissions..."
chmod +x main.py

echo ""
echo "========================================"
echo "✅ Installation Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. Review configuration in config/settings.py"
echo "  2. Update WEBHOOK_URL environment variable if needed"
echo "  3. Test the system:"
echo "     source venv/bin/activate"
echo "     python3 main.py"
echo ""
echo "  4. Enable autostart (optional):"
echo "     sudo systemctl enable security-cam"
echo "     sudo systemctl start security-cam"
echo ""
echo "  5. View logs:"
echo "     sudo journalctl -u security-cam -f"
echo ""

# Check if reboot needed
if grep -q "^dtparam=i2c_arm=on" /boot/config.txt && ! lsmod | grep -q i2c_dev; then
    echo "⚠️  REBOOT REQUIRED to enable I2C and camera"
    echo "    Run: sudo reboot"
fi

echo ""

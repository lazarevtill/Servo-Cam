#!/usr/bin/env bash
# Servo Cam installation helper for Raspberry Pi / Debian-based systems

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
SERVICE_NAME="servo-cam"
ENV_DIR="/etc/servo_cam"
ENV_FILE="${ENV_DIR}/servo_cam.env"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
PROJECT_NAME="Servo Cam"

SUDO=""
if [[ $EUID -ne 0 ]]; then
    if ! command -v sudo >/dev/null 2>&1; then
        echo "❌ This installer requires root privileges or sudo access."
        exit 1
    fi
    SUDO="sudo"
fi

log() {
    printf "\n[%s] %s\n" "${PROJECT_NAME}" "$1"
}

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "❌ Required command '$1' not found. Please install it and rerun."
        exit 1
    fi
}

log "Validating host environment"
require_command python3
require_command apt-get
require_command systemctl

ARCH="$(uname -m)"
case "${ARCH}" in
    arm*|aarch64)
        log "Detected ARM architecture (${ARCH})"
        ;;
    *)
        log "Warning: Detected non-ARM architecture (${ARCH}). Continuing anyway."
        ;;
esac

log "Updating package index"
${SUDO} apt-get update

APT_PACKAGES=(
    python3
    python3-venv
    python3-pip
    python3-opencv
    libatlas-base-dev
    libjpeg-dev
    libgl1
    libglib2.0-0
    libsm6
    libxext6
    libxrender1
    v4l-utils
    i2c-tools
    git
)

OPTIONAL_PACKAGES=(
    python3-picamera2
)

log "Installing required system packages"
${SUDO} apt-get install -y --no-install-recommends "${APT_PACKAGES[@]}"

log "Installing optional camera packages (best effort)"
for pkg in "${OPTIONAL_PACKAGES[@]}"; do
    if ! ${SUDO} apt-get install -y --no-install-recommends "${pkg}"; then
        echo "⚠️  Optional package '${pkg}' could not be installed. Continuing without it."
    fi
done

if command -v raspi-config >/dev/null 2>&1; then
    log "Attempting to enable I²C interface"
    if ! ${SUDO} raspi-config nonint do_i2c 0; then
        echo "⚠️  Unable to enable I²C automatically. Please enable it manually via 'sudo raspi-config'."
    fi
fi

log "Setting up Python virtual environment"
if [[ ! -d "${VENV_DIR}" ]]; then
    python3 -m venv "${VENV_DIR}"
fi

# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"
python3 -m pip install --upgrade pip wheel
pip install -r "${ROOT_DIR}/requirements.txt"
deactivate

SERVICE_USER="${SUDO_USER:-$USER}"
SERVICE_GROUP="$(id -gn "${SERVICE_USER}")"

log "Writing environment configuration to ${ENV_FILE}"
${SUDO} mkdir -p "${ENV_DIR}"
${SUDO} tee "${ENV_FILE}" >/dev/null <<EOF
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=false
LOG_LEVEL=INFO
# Override WEBHOOK_URL here if you do not want to use the default.
# WEBHOOK_URL=https://example.com/webhook
EOF

log "Creating systemd service ${SERVICE_NAME}"
${SUDO} tee "${SERVICE_FILE}" >/dev/null <<EOF
[Unit]
Description=${PROJECT_NAME} backend service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_GROUP}
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=-${ENV_FILE}
WorkingDirectory=${ROOT_DIR}
ExecStart=${VENV_DIR}/bin/python ${ROOT_DIR}/main.py
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF

log "Reloading systemd manager configuration"
${SUDO} systemctl daemon-reload

log "Enabling and starting ${SERVICE_NAME}.service"
${SUDO} systemctl enable --now "${SERVICE_NAME}.service"

log "Installation complete!"
cat <<'EOF'
----------------------------------------------------------------------
Next steps:
  • Verify the service: sudo systemctl status servo-cam.service
  • View logs:        journalctl -u servo-cam.service -f
  • In Home Assistant, add https://github.com/lazarevtill/Servo-Cam
    as an add-on repository, install the "Servo Cam" add-on, and
    complete the integration setup (auto-discovery or manual host/port).

If you need to tweak runtime settings, edit /etc/servo_cam/servo_cam.env
and run: sudo systemctl restart servo-cam.service
----------------------------------------------------------------------
EOF

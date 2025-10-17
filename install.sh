#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"
HA_CONFIG_DIR="${HA_CONFIG_DIR:-${HOME}/.homeassistant}"
INSTALL_SYSTEMD=${INSTALL_SYSTEMD:-0}
START_NOW=${START_NOW:-0}
SERVICE_NAME="security-cam"

usage() {
    cat <<'USAGE'
Usage: ./install.sh [options]

Options:
  --ha-config PATH   Override Home Assistant config directory (default: ~/.homeassistant if it exists)
  --systemd          Install or update the optional systemd unit for auto-start
  --start            Start or restart the Servo Cam service immediately
  -h, --help         Show this message and exit

Environment variables:
  HA_CONFIG_DIR      Same as --ha-config
  INSTALL_SYSTEMD    Set to 1 to enable --systemd behaviour without flag
  START_NOW          Set to 1 to mimic --start and launch the service immediately

The script installs required OS packages (if apt-get is available),
creates/updates a Python virtual environment in .venv, installs Python
dependencies, and copies the Servo Cam integration into the Home Assistant
configuration directory when present.
USAGE
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --ha-config)
            shift || { echo "Missing value for --ha-config" >&2; exit 1; }
            HA_CONFIG_DIR="$1"
            ;;
        --systemd)
            INSTALL_SYSTEMD=1
            ;;
        --start)
            START_NOW=1
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            usage
            exit 1
            ;;
    esac
    shift || true
done

sudo_cmd() {
    if command -v sudo >/dev/null 2>&1 && [[ "${EUID}" -ne 0 ]]; then
        sudo "$@"
    else
        "$@"
    fi
}

step() {
    echo
    echo "==> $1"
}

step "Checking prerequisites"
command -v python3 >/dev/null 2>&1 || { echo "python3 is required" >&2; exit 1; }
command -v pip3 >/dev/null 2>&1 || echo "Warning: pip3 not found in PATH; continuing" >&2

if command -v apt-get >/dev/null 2>&1; then
    step "Installing OS dependencies"
    sudo_cmd apt-get update
    sudo_cmd apt-get install -y \
        python3 python3-venv python3-pip python3-dev \
        libatlas-base-dev libopenjp2-7 libtiff5 libjpeg-dev \
        zlib1g-dev libilmbase-dev libopenexr-dev libgstreamer1.0-0 \
        libavcodec58 libavformat58 libswscale5
else
    echo "apt-get not found; skipping OS package installation"
fi

step "Creating virtual environment at ${VENV_DIR}"
python3 -m venv "${VENV_DIR}"
# shellcheck source=/dev/null
source "${VENV_DIR}/bin/activate"

step "Upgrading pip and wheel"
pip install --upgrade pip wheel

step "Installing Python dependencies"
pip install --upgrade -r "${PROJECT_ROOT}/requirements.txt"

if [[ -d "${HA_CONFIG_DIR}" ]]; then
    step "Copying Home Assistant integration into ${HA_CONFIG_DIR}/custom_components"
    mkdir -p "${HA_CONFIG_DIR}/custom_components"
    if command -v rsync >/dev/null 2>&1; then
        rsync --archive --delete "${PROJECT_ROOT}/custom_components/servo_cam" "${HA_CONFIG_DIR}/custom_components/"
    else
        echo "rsync not found; falling back to cp -r (delete old copy manually if needed)"
        rm -rf "${HA_CONFIG_DIR}/custom_components/servo_cam"
        cp -R "${PROJECT_ROOT}/custom_components/servo_cam" "${HA_CONFIG_DIR}/custom_components/"
    fi
else
    echo "Home Assistant config directory not found at ${HA_CONFIG_DIR}; skipping integration copy"
    echo "Set HA_CONFIG_DIR or pass --ha-config to override the path."
fi

deactivate >/dev/null 2>&1 || true

if [[ "${INSTALL_SYSTEMD}" -eq 1 ]]; then
    step "Installing systemd unit ${SERVICE_NAME}.service"
    RUN_USER="${SUDO_USER:-$USER}"
    SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}.service"
    SERVICE_TMP="$(mktemp)"
    cat > "${SERVICE_TMP}" <<SYSTEMD
[Unit]
Description=Servo Cam Security Camera
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${RUN_USER}
WorkingDirectory=${PROJECT_ROOT}
Environment="PATH=${VENV_DIR}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=${VENV_DIR}/bin/python3 ${PROJECT_ROOT}/main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
SYSTEMD
    sudo_cmd mv "${SERVICE_TMP}" "${SERVICE_PATH}"
    sudo_cmd systemctl daemon-reload
    sudo_cmd systemctl enable "${SERVICE_NAME}.service"
    echo "Systemd service installed at ${SERVICE_PATH}."
fi

if [[ "${START_NOW}" -eq 1 ]]; then
    step "Starting Servo Cam"
    if [[ "${INSTALL_SYSTEMD}" -eq 1 ]] && command -v systemctl >/dev/null 2>&1; then
        sudo_cmd systemctl restart "${SERVICE_NAME}.service"
        echo "Systemd service restarted. View logs with: sudo journalctl -u ${SERVICE_NAME} -f"
    else
        LOG_DIR="${PROJECT_ROOT}/logs"
        LOG_FILE="${LOG_DIR}/servo_cam.log"
        mkdir -p "${LOG_DIR}"

        if pgrep -f "${PROJECT_ROOT}/main.py" >/dev/null 2>&1; then
            echo "Existing Servo Cam process detected. Skipping new start."
        else
            "${VENV_DIR}/bin/python3" "${PROJECT_ROOT}/main.py" \
                >"${LOG_FILE}" 2>&1 &
            SERVICE_PID=$!
            echo "Started Servo Cam (PID: ${SERVICE_PID}). Logs: ${LOG_FILE}"
        fi
    fi
fi

echo
step "Servo Cam environment ready"
echo "To start the application manually:"
echo "  source ${VENV_DIR}/bin/activate"
echo "  python3 main.py"

echo
step "All done!"

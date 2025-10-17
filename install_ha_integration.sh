#!/bin/bash
# Installation script for Home Assistant Servo Camera Integration

set -e

echo "========================================"
echo "Servo Camera - Home Assistant Integration"
echo "Installation Script"
echo "========================================"
echo

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Detect Home Assistant installation
detect_ha_path() {
    if [ -d "/config" ]; then
        # Home Assistant OS / Supervised
        echo "/config"
    elif [ -d "$HOME/.homeassistant" ]; then
        # Home Assistant Core
        echo "$HOME/.homeassistant"
    else
        return 1
    fi
}

# Main installation
main() {
    echo "Step 1: Detecting Home Assistant installation..."

    HA_CONFIG_PATH=$(detect_ha_path)

    if [ -z "$HA_CONFIG_PATH" ]; then
        print_error "Home Assistant config directory not found"
        echo
        echo "Please specify your Home Assistant config path:"
        read -p "Path: " HA_CONFIG_PATH

        if [ ! -d "$HA_CONFIG_PATH" ]; then
            print_error "Directory does not exist: $HA_CONFIG_PATH"
            exit 1
        fi
    fi

    print_success "Found Home Assistant at: $HA_CONFIG_PATH"
    echo

    # Create custom_components directory if needed
    echo "Step 2: Preparing custom components directory..."
    CUSTOM_COMP_PATH="$HA_CONFIG_PATH/custom_components"

    if [ ! -d "$CUSTOM_COMP_PATH" ]; then
        mkdir -p "$CUSTOM_COMP_PATH"
        print_success "Created: $CUSTOM_COMP_PATH"
    else
        print_success "Directory exists: $CUSTOM_COMP_PATH"
    fi
    echo

    # Copy integration files
    echo "Step 3: Installing Servo Camera integration..."
    INTEGRATION_PATH="$CUSTOM_COMP_PATH/servo_cam"

    if [ -d "$INTEGRATION_PATH" ]; then
        print_warning "Integration already exists"
        read -p "Overwrite? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Installation cancelled"
            exit 0
        fi
        rm -rf "$INTEGRATION_PATH"
    fi

    # Get script directory
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
    SOURCE_PATH="$SCRIPT_DIR/custom_components/servo_cam"

    if [ ! -d "$SOURCE_PATH" ]; then
        print_error "Source integration not found at: $SOURCE_PATH"
        exit 1
    fi

    cp -r "$SOURCE_PATH" "$INTEGRATION_PATH"
    print_success "Copied integration files"
    echo

    # Verify installation
    echo "Step 4: Verifying installation..."

    if [ -f "$INTEGRATION_PATH/manifest.json" ]; then
        print_success "manifest.json found"
    else
        print_error "manifest.json missing"
        exit 1
    fi

    if [ -f "$INTEGRATION_PATH/__init__.py" ]; then
        print_success "__init__.py found"
    else
        print_error "__init__.py missing"
        exit 1
    fi

    if [ -f "$INTEGRATION_PATH/config_flow.py" ]; then
        print_success "config_flow.py found"
    else
        print_error "config_flow.py missing"
        exit 1
    fi

    echo

    # Show next steps
    echo "========================================"
    echo "Installation Complete!"
    echo "========================================"
    echo
    echo "Next steps:"
    echo "1. Restart Home Assistant"
    echo "   - Supervisor: Settings → System → Restart"
    echo "   - Docker: docker restart homeassistant"
    echo "   - Core: systemctl restart home-assistant@homeassistant"
    echo
    echo "2. Add the integration:"
    echo "   - Go to Settings → Devices & Services"
    echo "   - Click '+ Add Integration'"
    echo "   - Search for 'Servo Security Camera'"
    echo "   - Enter your Raspberry Pi IP and port 5000"
    echo
    echo "3. Documentation:"
    echo "   - Integration README: custom_components/servo_cam/README.md"
    echo "   - Full guide: HOMEASSISTANT_INTEGRATION.md"
    echo
    print_success "Integration installed at: $INTEGRATION_PATH"
}

# Run main
main

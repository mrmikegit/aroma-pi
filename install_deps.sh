#!/bin/bash
# Script to install all dependencies including rpi-lgpio

cd "$(dirname "$0")"

echo "Installing build dependencies and system libraries..."
sudo apt install swig python3-dev build-essential -y

# Check if python3-lgpio is available as system package
echo "Checking for system lgpio package..."
if apt list --installed 2>/dev/null | grep -q python3-lgpio; then
    echo "python3-lgpio is already installed"
elif apt-cache search python3-lgpio 2>/dev/null | grep -q python3-lgpio; then
    echo "Installing python3-lgpio from system repositories..."
    sudo apt install python3-lgpio -y
else
    echo "python3-lgpio not available in repositories, will build from source"
fi

echo "Installing Python dependencies..."
if [ ! -d "venv" ]; then
    echo "Creating virtual environment with system site packages..."
    echo "This allows access to system-installed python3-lgpio"
    python3 -m venv --system-site-packages venv
fi

echo "Installing packages..."
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

# Try to install rpi-lgpio, but don't fail if system package is available
echo "Attempting to install rpi-lgpio..."
if ./venv/bin/pip install rpi-lgpio 2>&1 | grep -q "ERROR"; then
    echo "Warning: Could not install rpi-lgpio from pip"
    echo "Will use system-installed python3-lgpio (if available)"
    if python3 -c "import lgpio" 2>/dev/null; then
        echo "✓ System lgpio is available and will be used"
    else
        echo "✗ lgpio not available. You may need to install python3-lgpio:"
        echo "  sudo apt install python3-lgpio -y"
    fi
else
    echo "✓ rpi-lgpio installed successfully"
fi

echo ""
echo "Installation complete!"
echo "You can now run ./start.sh"


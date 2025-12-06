#!/bin/bash
# Script to install all dependencies for the Oil Diffuser Control System

cd "$(dirname "$0")"

echo "Installing system dependencies..."
sudo apt install python3-pip python3-venv python3-gpiozero python3-lgpio -y

echo "Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    echo "Creating virtual environment with system site packages..."
    python3 -m venv --system-site-packages venv
else
    echo "Virtual environment already exists"
fi

echo "Installing Python packages..."
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

# Verify lgpio is available
echo ""
echo "Verifying lgpio installation..."
if ./venv/bin/python -c "import lgpio" 2>/dev/null; then
    echo "✓ lgpio is available"
else
    echo "✗ lgpio not available. Make sure python3-lgpio is installed:"
    echo "  sudo apt install python3-lgpio -y"
    exit 1
fi

echo ""
echo "Installation complete!"
echo "You can now run: ./start.sh"

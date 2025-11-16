#!/bin/bash
# Start script for Oil Diffuser Control System

cd "$(dirname "$0")"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Creating..."
    python3 -m venv venv
    echo "Installing dependencies..."
    ./venv/bin/pip install -r requirements.txt
fi

# Start the application
echo "Starting Oil Diffuser Control System..."
./venv/bin/python app.py


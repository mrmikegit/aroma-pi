# Oil Diffuser Control System

A web-based control system for a waterless oil diffuser connected to an HVAC system, designed to run on Raspberry Pi 5.

## Features

- **HVAC Fan Monitoring**: Automatically detects when the HVAC blower fan is running
- **Smart Activation**: Waits 10 seconds after detecting HVAC fan before starting diffuser
- **Configurable Duty Cycles**: 10 different intensity levels (on/off time combinations)
- **Business Hours Control**: Optional scheduling to run only during specified hours
- **Real-time Status**: Live display of HVAC, pump, and fan states
- **Runtime Tracking**: Monitors and displays total runtime for pump and fan
- **Historical Chart**: 24-hour visualization of HVAC fan state
- **Persistent Settings**: All configurations saved and restored after reboot
- **Push Alerts**: Optional web push notifications (including iOS via Add to Home Screen) when the oil tank is empty or via manual test button

## Hardware Requirements

- Raspberry Pi 5
- GPIO Connections:
  - GPIO25: Air pump control (output)
  - GPIO24: 12V fan control (output)
  - GPIO16: HVAC blower fan state (input, no internal pulldown)

## Installation

1. **Update system packages:**
   ```bash
   sudo apt update
   sudo apt full-upgrade -y
   ```

2. **Install Python and pip:**
   ```bash
   sudo apt install python3-pip python3-venv python3-gpiozero python3-lgpio -y
   ```
   
   Note: `gpiozero` with `lgpio` backend is used for Raspberry Pi 5 compatibility.
   The `lgpio` library is required for GPIO access on Raspberry Pi 5.

3. **Create virtual environment (required):**
   ```bash
   python3 -m venv venv
   ```

4. **Install build dependencies for rpi-lgpio:**
   ```bash
   sudo apt install swig python3-dev build-essential -y
   ```
   
   If available, also install the system package:
   ```bash
   sudo apt install python3-lgpio -y
   ```
   
   Or use the install script:
   ```bash
   ./install_deps.sh
   ```
    
5. **Install Python dependencies:**
   ```bash
   ./venv/bin/pip install -r requirements.txt
   ```
   The requirements include `pywebpush` and `cryptography` for push notifications.

5. **Install Python dependencies:**
   ```bash
   ./venv/bin/pip install -r requirements.txt
   ./venv/bin/pip install rpi-lgpio
   ```
   
   Or activate the virtual environment first:
   ```bash
   source venv/bin/activate
   pip install -r requirements.txt
   pip install rpi-lgpio
   ```

6. **Set up GPIO permissions (if needed):**
   ```bash
   sudo usermod -a -G gpio $USER
   ```
   (You may need to log out and back in for this to take effect)

## Usage

1. **Start the application:**
   
   Easiest way (using the start script):
   ```bash
   ./start.sh
   ```
   
   Or using the virtual environment directly:
   ```bash
   ./venv/bin/python app.py
   ```
   
   Or activate the virtual environment first:
   ```bash
   source venv/bin/activate
   python app.py
   ```

2. **Access the web interface:**
   Open a web browser and navigate to:
   ```
   http://raspberry-pi-ip-address:8080
   ```
   Or if running locally:
   ```
   http://localhost:8080
   ```

3. **Configure the system:**
   - Enable/disable the aroma system
   - Select desired intensity (duty cycle)
   - Optionally enable business hours
   - Monitor real-time status and runtime

## Duty Cycles

The system supports 10 different intensity levels:

| On Time | Off Time | Intensity |
|---------|----------|-----------|
| 60s     | 240s     | Very Low  |
| 60s     | 120s     | Low       |
| 60s     | 90s      | Medium-Low|
| 60s     | 60s      | Medium    |
| 60s     | 45s      | Medium-High|
| 60s     | 30s      | High      |
| 90s     | 30s      | Very High |
| 120s    | 30s      | Very High |
| 240s    | 30s      | Maximum   |
| 360s    | 30s      | Maximum   |

## Operation Logic

1. The system polls GPIO16 every 5 seconds to check HVAC fan state
2. When HVAC fan is detected (logic LOW), the system waits 10 seconds
3. After the delay, the diffuser starts operating with the selected duty cycle
4. The diffuser only runs when:
   - System is enabled
   - HVAC fan is running
   - Within business hours (if enabled)

## Auto-Start on Boot

To run the application automatically on boot, set up a systemd service:

1. **Copy the service file to systemd directory:**
   ```bash
   sudo cp aroma-pi.service /etc/systemd/system/
   ```

2. **Edit the service file to match your setup (if needed):**
   ```bash
   sudo nano /etc/systemd/system/aroma-pi.service
   ```
   
   Update the following if your paths are different:
   - `User=pi` - Change to your username if different
   - `WorkingDirectory=/home/pi/aroma-pi` - Change to your actual path
   - `ExecStart=/home/pi/aroma-pi/venv/bin/python` - Change to your venv path

3. **Reload systemd and enable the service:**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable aroma-pi.service
   ```

4. **Start the service:**
   ```bash
   sudo systemctl start aroma-pi.service
   ```

5. **Check service status:**
   ```bash
   sudo systemctl status aroma-pi.service
   ```

6. **View service logs (to debug GPIO issues):**
   ```bash
   sudo journalctl -u aroma-pi.service -f
   ```

**Useful commands:**
- Stop the service: `sudo systemctl stop aroma-pi.service`
- Restart the service: `sudo systemctl restart aroma-pi.service`
- Disable auto-start: `sudo systemctl disable aroma-pi.service`
- Check if service is enabled: `sudo systemctl is-enabled aroma-pi.service`

## Push Notifications

The app can send web push notifications (including iOS 16.4+ web push when the site is added to the home screen). Notifications are triggered automatically when the oil tank reaches 0% and can be tested via the “Send Test Notification” button in the Control Panel.

1. **HTTPS is required** (you already have this via Cloudflare Zero Trust tunnel). Browsers (especially iOS) only allow service workers and push notifications on secure origins.
2. **Install to Home Screen on iOS**: After opening the site in Safari, tap share → “Add to Home Screen”. Push notifications only work for installed web apps on iOS.
3. **Enable notifications in the UI**: Use the “Enable Notifications” button to grant permission and subscribe the current browser.
4. **VAPID keys**: On first run the server automatically generates a `vapid.json` file. You can replace it with your own keys if desired.
5. **Subscriptions**: Stored in `subscriptions.json`. If a device unregisters, stale subscriptions are removed automatically the next time a notification is sent.

Push endpoints exposed by the server:

- `GET /api/vapid-public-key` – returns the public VAPID key.
- `POST /api/subscribe` – stores a new push subscription (called by the browser).
- `POST /api/test_notification` – sends a test notification to all active subscribers.

If you change domains or certificates, users must re-enable notifications so the browser can create a new subscription.

## File Structure

```
aroma/
├── app.py              # Main Flask application
├── requirements.txt    # Python dependencies
├── config.json         # Saved settings (auto-generated)
├── history.json        # HVAC history data (auto-generated)
├── templates/
│   └── index.html      # Web interface
└── static/
    ├── css/
    │   └── style.css   # Stylesheet
    └── js/
        └── app.js      # Frontend JavaScript
```

## API Endpoints

- `GET /` - Main web interface
- `GET /api/status` - Get current system status
- `GET /api/history` - Get HVAC history (last 24 hours)
- `GET /api/duty_cycles` - Get available duty cycles
- `POST /api/settings` - Update system settings
- `POST /api/reset_counters` - Reset runtime counters

## Troubleshooting

- **GPIO not working**: Ensure you have GPIO permissions and RPi.GPIO is installed
- **Web interface not accessible**: Check firewall settings and ensure port 8080 is open
- **Settings not persisting**: Check file permissions on `config.json` and `history.json`

## Development Mode

For development on a non-Raspberry Pi system, the application will use mock GPIO that prints to console instead of controlling actual pins.

## License

This project is provided as-is for personal use.


#!/usr/bin/env python3
"""
Waterless Oil Diffuser Control System for Raspberry Pi 5
Controls diffuser based on HVAC fan state with configurable duty cycles
"""

import json
import os
import threading
import time
from datetime import datetime, time as dt_time
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS

# GPIO imports - use gpiozero for Pi 5 support, mock for development
try:
    from gpiozero import OutputDevice, InputDevice
    # Try to use lgpio pin factory for Raspberry Pi 5
    lgpio_imported = False
    try:
        import lgpio
        lgpio_imported = True
        # Add compatibility shim for old/new lgpio constant names
        # New lgpio uses SET_PULL_*, old uses SET_BIAS_*
        # gpiozero may expect old names, so create aliases
        if hasattr(lgpio, 'SET_PULL_NONE') and not hasattr(lgpio, 'SET_BIAS_DISABLE'):
            # New version - create old constant aliases for gpiozero compatibility
            lgpio.SET_BIAS_DISABLE = lgpio.SET_PULL_NONE
        elif hasattr(lgpio, 'SET_BIAS_DISABLE') and not hasattr(lgpio, 'SET_PULL_NONE'):
            # Old version - create new constant aliases
            lgpio.SET_PULL_NONE = lgpio.SET_BIAS_DISABLE
        
        if hasattr(lgpio, 'SET_PULL_UP') and not hasattr(lgpio, 'SET_BIAS_PULL_UP'):
            lgpio.SET_BIAS_PULL_UP = lgpio.SET_PULL_UP
        elif hasattr(lgpio, 'SET_BIAS_PULL_UP') and not hasattr(lgpio, 'SET_PULL_UP'):
            lgpio.SET_PULL_UP = lgpio.SET_BIAS_PULL_UP
        
        if hasattr(lgpio, 'SET_PULL_DOWN') and not hasattr(lgpio, 'SET_BIAS_PULL_DOWN'):
            lgpio.SET_BIAS_PULL_DOWN = lgpio.SET_PULL_DOWN
        elif hasattr(lgpio, 'SET_BIAS_PULL_DOWN') and not hasattr(lgpio, 'SET_PULL_DOWN'):
            lgpio.SET_PULL_DOWN = lgpio.SET_BIAS_PULL_DOWN
        
        from gpiozero.pins.lgpio import LGPIOFactory
        from gpiozero import Device
        Device.pin_factory = LGPIOFactory()
        print("Using lgpio pin factory for Raspberry Pi 5")
    except ImportError as e:
        # lgpio not available - check if system package exists
        print(f"lgpio not found in venv ({e})")
        import sys
        # Check if venv has system-site-packages enabled
        if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
            # We're in a venv
            import sysconfig
            if '--system-site-packages' not in sysconfig.get_config_var('CONFIG_ARGS') or '':
                print("WARNING: Virtual environment was not created with --system-site-packages")
                print("To fix, run:")
                print("  rm -rf venv")
                print("  python3 -m venv --system-site-packages venv")
                print("  ./venv/bin/pip install -r requirements.txt")
        
        # Try to add system paths manually
        try:
            import sys
            system_paths = [
                '/usr/lib/python3/dist-packages',
                f'/usr/lib/python3.{sys.version_info.minor}/dist-packages',
            ]
            for path in system_paths:
                if path not in sys.path:
                    sys.path.insert(0, path)
            # Try importing again
            import lgpio
            lgpio_imported = True
            print(f"Successfully imported lgpio from system packages")
        except Exception as e2:
            print(f"Could not import lgpio from system: {e2}")
            print("Install with: sudo apt install python3-lgpio -y")
            print("Then recreate venv: rm -rf venv && python3 -m venv --system-site-packages venv")
    except Exception as e:
        # Other error setting up lgpio factory
        print(f"Note: Could not set up lgpio pin factory ({e})")
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError, OSError) as e:
    print(f"Warning: gpiozero not available ({e}), using mock GPIO")
    GPIO_AVAILABLE = False
    # Mock GPIO for development
    class MockOutputDevice:
        def __init__(self, pin):
            self.pin = pin
            self._value = False
        
        def on(self):
            print(f"Mock GPIO: Pin {self.pin} = ON")
            self._value = True
        
        def off(self):
            print(f"Mock GPIO: Pin {self.pin} = OFF")
            self._value = False
        
        def close(self):
            pass
    
    class MockInputDevice:
        def __init__(self, pin, pull_up=None):
            self.pin = pin
            # Mock: return False (LOW, fan on) for testing
            self._value = False
        
        @property
        def value(self):
            return 0  # LOW = fan on
        
        @property
        def is_active(self):
            return False  # LOW = active (fan on)
        
        def close(self):
            pass
    
    OutputDevice = MockOutputDevice
    InputDevice = MockInputDevice

app = Flask(__name__)
CORS(app)

# GPIO Pin Definitions
GPIO_PUMP = 25      # Air pump control
GPIO_FAN = 24       # 12V fan control
GPIO_HVAC = 16      # HVAC blower fan state (LOW = on, HIGH = off)

# Configuration file
CONFIG_FILE = 'config.json'
HISTORY_FILE = 'history.json'

# Duty cycle presets (on_time, off_time in seconds)
DUTY_CYCLES = {
    '60s_240s': (60, 240),
    '60s_120s': (60, 120),
    '60s_90s': (60, 90),
    '60s_60s': (60, 60),
    '60s_45s': (60, 45),
    '60s_30s': (60, 30),
    '90s_30s': (90, 30),
    '120s_30s': (120, 30),
    '240s_30s': (240, 30),
    '360s_30s': (360, 30),
}

# Global state
state = {
    'enabled': False,
    'duty_cycle': '60s_120s',
    'business_hours_enabled': False,
    'business_hours_start': '09:00',
    'business_hours_end': '17:00',
    'oil_usage_rate_ml_per_hour': 10.0,
    'oil_bottle_capacity_ml': 500.0,
    'hvac_fan_state': False,
    'pump_on': False,
    'fan_on': False,
    'pump_runtime_minutes': 0,
    'fan_runtime_minutes': 0,
    'last_pump_start': None,
    'last_fan_start': None,
}

# Control flags
control_thread = None
monitoring_thread = None
stop_flag = threading.Event()
hvac_history = []  # List of (timestamp, state) tuples

# GPIO device objects
gpio_pump = None
gpio_fan = None
gpio_hvac = None
lgpio_handle = None  # lgpio handle for direct pin configuration

def load_config():
    """Load configuration from file"""
    global state
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                saved_state = json.load(f)
                state.update(saved_state)
                print(f"Loaded config: {saved_state}")
        except Exception as e:
            print(f"Error loading config: {e}")

def save_config():
    """Save configuration to file"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"Error saving config: {e}")

def load_history():
    """Load HVAC history from file"""
    global hvac_history
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                data = json.load(f)
                hvac_history = [(datetime.fromisoformat(ts), s) for ts, s in data]
        except Exception as e:
            print(f"Error loading history: {e}")

def save_history():
    """Save HVAC history to file (keep last 24 hours)"""
    try:
        # Keep only last 24 hours
        cutoff = datetime.now().timestamp() - (24 * 3600)
        recent_history = [(ts.isoformat(), s) for ts, s in hvac_history 
                         if ts.timestamp() > cutoff]
        
        with open(HISTORY_FILE, 'w') as f:
            json.dump(recent_history, f)
    except Exception as e:
        print(f"Error saving history: {e}")

def init_gpio():
    """Initialize GPIO pins"""
    global gpio_pump, gpio_fan, gpio_hvac, GPIO_AVAILABLE, lgpio_handle
    
    if not GPIO_AVAILABLE:
        return
    
    try:
        # Initialize output devices (pump and fan)
        gpio_pump = OutputDevice(GPIO_PUMP, active_high=True, initial_value=False)
        gpio_fan = OutputDevice(GPIO_FAN, active_high=True, initial_value=False)
        
        # Initialize input device (HVAC state) - no pull resistor
        # First, configure the pin using lgpio directly
        try:
            import lgpio
            handle = lgpio.gpiochip_open(0)
            
            # Claim GPIO16 as input
            lgpio.gpio_claim_input(handle, GPIO_HVAC)
            
            # Set GPIO16 to no pull resistor
            try:
                lgpio.gpio_set_pull(handle, GPIO_HVAC, lgpio.SET_PULL_NONE)
                print(f"GPIO{GPIO_HVAC} configured with SET_PULL_NONE via lgpio")
            except AttributeError:
                # Try alternative function name if gpio_set_pull doesn't exist
                try:
                    lgpio.gpio_set_pull_config(handle, GPIO_HVAC, lgpio.SET_PULL_NONE)
                    print(f"GPIO{GPIO_HVAC} configured with SET_PULL_NONE via lgpio (alt method)")
                except AttributeError:
                    print(f"Warning: Could not set pull resistor - using default configuration")
            
            # Store handle for direct reading
            # We'll use lgpio directly for reading since we've configured it manually
            # This avoids gpiozero's constant compatibility issues
            lgpio_handle = handle
            gpio_hvac = None  # We'll use lgpio directly for reading
            print(f"GPIO{GPIO_HVAC} configured, will use lgpio directly for reading")
        except ImportError:
            # lgpio not available, try with gpiozero's pull parameter
            print("lgpio not available, trying gpiozero pull parameter...")
            try:
                gpio_hvac = InputDevice(GPIO_HVAC, pull=None)
            except Exception as e:
                print(f"Warning: Could not set pull=None, trying alternative: {e}")
                from gpiozero.pins.native import NativeFactory
                factory = NativeFactory()
                gpio_hvac = InputDevice(GPIO_HVAC, pull=None, pin_factory=factory)
            lgpio_handle = None
        
        print(f"GPIO initialized: Pump={GPIO_PUMP}, Fan={GPIO_FAN}, HVAC={GPIO_HVAC}")
    except Exception as e:
        print(f"Error initializing GPIO: {e}")
        GPIO_AVAILABLE = False

def cleanup_gpio():
    """Cleanup GPIO pins"""
    global gpio_pump, gpio_fan, gpio_hvac, lgpio_handle
    
    if gpio_pump:
        gpio_pump.close()
        gpio_pump = None
    if gpio_fan:
        gpio_fan.close()
        gpio_fan = None
    if gpio_hvac:
        gpio_hvac.close()
        gpio_hvac = None
    if lgpio_handle is not None:
        try:
            import lgpio
            lgpio.gpiochip_close(lgpio_handle)
        except:
            pass
        lgpio_handle = None

def is_business_hours():
    """Check if current time is within business hours"""
    if not state['business_hours_enabled']:
        return True
    
    try:
        start_time = dt_time.fromisoformat(state['business_hours_start'])
        end_time = dt_time.fromisoformat(state['business_hours_end'])
        current_time = datetime.now().time()
        
        if start_time <= end_time:
            return start_time <= current_time <= end_time
        else:  # Span midnight
            return current_time >= start_time or current_time <= end_time
    except Exception as e:
        print(f"Error checking business hours: {e}")
        return True

def update_runtime_counters():
    """Update runtime counters based on current state"""
    now = datetime.now()
    
    if state['pump_on']:
        if state['last_pump_start']:
            # Accumulate time since last check (1 second intervals)
            elapsed = 1.0 / 60.0  # 1 second in minutes
            state['pump_runtime_minutes'] += elapsed
        else:
            # Just turned on, record start time
            state['last_pump_start'] = now
    else:
        # Just turned off, clear start time
        if state['last_pump_start']:
            state['last_pump_start'] = None
    
    if state['fan_on']:
        if state['last_fan_start']:
            # Accumulate time since last check (1 second intervals)
            elapsed = 1.0 / 60.0  # 1 second in minutes
            state['fan_runtime_minutes'] += elapsed
        else:
            # Just turned on, record start time
            state['last_fan_start'] = now
    else:
        # Just turned off, clear start time
        if state['last_fan_start']:
            state['last_fan_start'] = None

def set_pump(on):
    """Control the air pump"""
    global gpio_pump
    
    if state['pump_on'] == on:
        return  # No change needed
    
    if GPIO_AVAILABLE and gpio_pump:
        if on:
            gpio_pump.on()
        else:
            gpio_pump.off()
    
    state['pump_on'] = on
    if on and not state['last_pump_start']:
        state['last_pump_start'] = datetime.now()

def set_fan(on):
    """Control the 12V fan"""
    global gpio_fan
    
    if state['fan_on'] == on:
        return  # No change needed
    
    if GPIO_AVAILABLE and gpio_fan:
        if on:
            gpio_fan.on()
        else:
            gpio_fan.off()
    
    state['fan_on'] = on
    if on and not state['last_fan_start']:
        state['last_fan_start'] = datetime.now()

def read_hvac_state():
    """Read HVAC blower fan state (LOW = on, HIGH = off)"""
    global gpio_hvac, lgpio_handle
    
    if GPIO_AVAILABLE:
        if gpio_hvac:
            # Use gpiozero to read
            # gpiozero: value is 0 for LOW, 1 for HIGH
            # LOW (0) means HVAC fan is on
            return gpio_hvac.value == 0
        elif lgpio_handle is not None:
            # Use lgpio directly to read
            try:
                import lgpio
                raw_value = lgpio.gpio_read(lgpio_handle, GPIO_HVAC)
                return raw_value == 0  # LOW = on
            except:
                return False
    else:
        # Mock: return True for testing
        return True

def hvac_monitoring_thread():
    """Monitor HVAC fan state every 5 seconds"""
    global hvac_history
    
    hvac_detected = False
    hvac_detected_time = None
    
    while not stop_flag.is_set():
        try:
            hvac_state = read_hvac_state()
            state['hvac_fan_state'] = hvac_state
            
            # Record history
            hvac_history.append((datetime.now(), hvac_state))
            
            # Keep only last 24 hours in memory
            cutoff = datetime.now().timestamp() - (24 * 3600)
            hvac_history = [(ts, s) for ts, s in hvac_history 
                           if ts.timestamp() > cutoff]
            
            # Save history periodically (every 5 minutes)
            if len(hvac_history) % 60 == 0:
                save_history()
            
            # Detect HVAC fan turning on
            if hvac_state and not hvac_detected:
                hvac_detected = True
                hvac_detected_time = time.time()
            elif not hvac_state:
                hvac_detected = False
                hvac_detected_time = None
            
            time.sleep(5)
        except Exception as e:
            print(f"Error in HVAC monitoring: {e}")
            time.sleep(5)

def control_thread_func():
    """Main control thread for diffuser operation"""
    hvac_detected = False
    hvac_detected_time = None
    pump_on = False
    fan_on = False
    duty_cycle_start = None
    on_phase = True
    
    while not stop_flag.is_set():
        try:
            # Update runtime counters
            update_runtime_counters()
            
            # Check if system is enabled
            if not state['enabled']:
                if pump_on or fan_on:
                    set_pump(False)
                    set_fan(False)
                    pump_on = False
                    fan_on = False
                    duty_cycle_start = None
                time.sleep(1)
                continue
            
            # Check business hours
            if not is_business_hours():
                if pump_on or fan_on:
                    set_pump(False)
                    set_fan(False)
                    pump_on = False
                    fan_on = False
                    duty_cycle_start = None
                time.sleep(1)
                continue
            
            # Check HVAC state
            hvac_state = state['hvac_fan_state']
            
            if hvac_state:
                if not hvac_detected:
                    hvac_detected = True
                    hvac_detected_time = time.time()
                
                # Wait 10 seconds after detecting HVAC fan
                if hvac_detected_time and (time.time() - hvac_detected_time) >= 10:
                    # Get current duty cycle
                    on_time, off_time = DUTY_CYCLES.get(state['duty_cycle'], (60, 120))
                    
                    if duty_cycle_start is None:
                        duty_cycle_start = time.time()
                        on_phase = True
                    
                    elapsed = time.time() - duty_cycle_start
                    
                    if on_phase:
                        if elapsed >= on_time:
                            # Switch to off phase
                            on_phase = False
                            duty_cycle_start = time.time()
                            set_pump(False)
                            set_fan(False)
                            pump_on = False
                            fan_on = False
                        else:
                            # Keep pump and fan on
                            if not pump_on or not fan_on:
                                set_pump(True)
                                set_fan(True)
                                pump_on = True
                                fan_on = True
                    else:
                        if elapsed >= off_time:
                            # Switch to on phase
                            on_phase = True
                            duty_cycle_start = time.time()
                        else:
                            # Keep pump and fan off
                            if pump_on or fan_on:
                                set_pump(False)
                                set_fan(False)
                                pump_on = False
                                fan_on = False
                else:
                    # Still waiting for 10 second delay
                    if pump_on or fan_on:
                        set_pump(False)
                        set_fan(False)
                        pump_on = False
                        fan_on = False
                    duty_cycle_start = None
            else:
                # HVAC fan is off
                hvac_detected = False
                hvac_detected_time = None
                if pump_on or fan_on:
                    set_pump(False)
                    set_fan(False)
                    pump_on = False
                    fan_on = False
                duty_cycle_start = None
            
            time.sleep(1)
        except Exception as e:
            print(f"Error in control thread: {e}")
            time.sleep(1)

def start_threads():
    """Start monitoring and control threads"""
    global monitoring_thread, control_thread
    
    if monitoring_thread is None or not monitoring_thread.is_alive():
        monitoring_thread = threading.Thread(target=hvac_monitoring_thread, daemon=True)
        monitoring_thread.start()
    
    if control_thread is None or not control_thread.is_alive():
        control_thread = threading.Thread(target=control_thread_func, daemon=True)
        control_thread.start()

# Flask Routes
@app.route('/')
def index():
    """Serve main page"""
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    """Get current system status"""
    update_runtime_counters()
    
    # Calculate oil remaining
    pump_runtime_hours = state['pump_runtime_minutes'] / 60.0
    oil_used_ml = pump_runtime_hours * state['oil_usage_rate_ml_per_hour']
    oil_remaining_ml = max(0, state['oil_bottle_capacity_ml'] - oil_used_ml)
    oil_percentage = (oil_remaining_ml / state['oil_bottle_capacity_ml'] * 100) if state['oil_bottle_capacity_ml'] > 0 else 0
    
    status = state.copy()
    status['oil_remaining_ml'] = round(oil_remaining_ml, 1)
    status['oil_percentage'] = round(oil_percentage, 1)
    status['oil_used_ml'] = round(oil_used_ml, 1)
    
    return jsonify(status)

@app.route('/api/history')
def get_history():
    """Get HVAC history for last 24 hours"""
    cutoff = datetime.now().timestamp() - (24 * 3600)
    recent_history = [(ts.isoformat(), s) for ts, s in hvac_history 
                     if ts.timestamp() > cutoff]
    return jsonify(recent_history)

@app.route('/api/duty_cycles')
def get_duty_cycles():
    """Get available duty cycles"""
    cycles = {}
    for key, (on, off) in DUTY_CYCLES.items():
        cycles[key] = {
            'on': on,
            'off': off,
            'label': f'{on}s / {off}s'
        }
    return jsonify(cycles)

@app.route('/api/settings', methods=['POST'])
def update_settings():
    """Update system settings"""
    data = request.json
    
    if 'enabled' in data:
        state['enabled'] = bool(data['enabled'])
    
    if 'duty_cycle' in data:
        if data['duty_cycle'] in DUTY_CYCLES:
            state['duty_cycle'] = data['duty_cycle']
    
    if 'business_hours_enabled' in data:
        state['business_hours_enabled'] = bool(data['business_hours_enabled'])
    
    if 'business_hours_start' in data:
        state['business_hours_start'] = data['business_hours_start']
    
    if 'business_hours_end' in data:
        state['business_hours_end'] = data['business_hours_end']
    
    if 'oil_usage_rate_ml_per_hour' in data:
        try:
            state['oil_usage_rate_ml_per_hour'] = float(data['oil_usage_rate_ml_per_hour'])
        except (ValueError, TypeError):
            pass
    
    if 'oil_bottle_capacity_ml' in data:
        try:
            state['oil_bottle_capacity_ml'] = float(data['oil_bottle_capacity_ml'])
        except (ValueError, TypeError):
            pass
    
    save_config()
    return jsonify({'success': True, 'state': state})

@app.route('/api/reset_counters', methods=['POST'])
def reset_counters():
    """Reset runtime counters"""
    state['pump_runtime_minutes'] = 0
    state['fan_runtime_minutes'] = 0
    state['last_pump_start'] = None
    state['last_fan_start'] = None
    save_config()
    return jsonify({'success': True})

if __name__ == '__main__':
    # Initialize
    load_config()
    load_history()
    init_gpio()
    start_threads()
    
    try:
        # Run Flask app
        app.run(host='0.0.0.0', port=8080, debug=False, threaded=True)
    finally:
        stop_flag.set()
        cleanup_gpio()
        save_config()
        save_history()


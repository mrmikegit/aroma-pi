#!/usr/bin/env python3
"""
Test script to read and display HVAC fan state from GPIO16
Reads the state every 5 seconds and displays it on screen
"""

import time
import sys

# GPIO Pin Definition
GPIO_HVAC = 16  # HVAC blower fan state (LOW = on, HIGH = off)

# Try to use gpiozero with lgpio
try:
    from gpiozero import InputDevice
    # Try to use lgpio pin factory for Raspberry Pi 5
    try:
        from gpiozero.pins.lgpio import LGPIOFactory
        from gpiozero import Device
        Device.pin_factory = LGPIOFactory()
        print("Using lgpio pin factory for Raspberry Pi 5")
    except (ImportError, Exception) as e:
        print(f"Note: Using default pin factory ({e})")
    
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError, OSError) as e:
    print(f"Error: gpiozero not available ({e})")
    print("Make sure gpiozero and rpi-lgpio are installed")
    sys.exit(1)

# Global variables
gpio_hvac = None
lgpio_handle = None

def read_hvac_state():
    """Read HVAC blower fan state (LOW = on, HIGH = off)"""
    global gpio_hvac, lgpio_handle
    
    if gpio_hvac:
        # Use gpiozero to read
        # gpiozero: value is 0 for LOW, 1 for HIGH
        # LOW (0) means HVAC fan is on
        raw_value = gpio_hvac.value
        is_on = raw_value == 0
        return is_on, raw_value
    elif lgpio_handle is not None:
        # Use lgpio directly to read
        import lgpio
        raw_value = lgpio.gpio_read(lgpio_handle, GPIO_HVAC)
        is_on = raw_value == 0  # LOW = on
        return is_on, raw_value
    return None, None

def main():
    global gpio_hvac, lgpio_handle
    
    print("HVAC Fan State Test Script")
    print("=" * 50)
    print(f"Monitoring GPIO{GPIO_HVAC} (LOW = fan ON, HIGH = fan OFF)")
    print("Press Ctrl+C to stop")
    print("=" * 50)
    print()
    
    try:
        # Initialize input device (HVAC state) - no pull resistor
        print(f"Initializing GPIO{GPIO_HVAC} as input with no pull resistor...")
        
        # Configure the pin using lgpio directly with SET_BIAS_DISABLE
        import lgpio
        handle = lgpio.gpiochip_open(0)
        
        # Claim GPIO16 as input with bias disabled (no internal pull-up or pull-down)
        try:
            lgpio.gpio_claim_input(handle, GPIO_HVAC, lgpio.SET_BIAS_DISABLE)
            print(f"✓ GPIO{GPIO_HVAC} configured as input with SET_BIAS_DISABLE (no internal pull)")
        except AttributeError:
            # Fallback if SET_BIAS_DISABLE doesn't exist - try older constants
            try:
                # Try with numeric value (SET_BIAS_DISABLE = 0x80000)
                lgpio.gpio_claim_input(handle, GPIO_HVAC, 0x80000)
                print(f"✓ GPIO{GPIO_HVAC} configured as input with bias disabled (numeric flag)")
            except Exception as e:
                # Last resort: claim without flags
                lgpio.gpio_claim_input(handle, GPIO_HVAC)
                print(f"⚠ Could not disable internal pull resistor - {e}")
        
        # We'll use lgpio directly for reading
        gpio_hvac = None
        
        # Store handle for direct reading
        lgpio_handle = handle
        
        print()
        print("Starting monitoring (every 5 seconds)...")
        print()
        
        iteration = 0
        while True:
            iteration += 1
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            
            # Read the state
            is_on, raw_value = read_hvac_state()
            
            if is_on is not None:
                status = "ON" if is_on else "OFF"
                raw_status = f"LOW (0)" if raw_value == 0 else f"HIGH (1)"
                print(f"[{timestamp}] #{iteration:4d} | State: {status:3s} | Raw: {raw_status:8s} | Pin Value: {raw_value}")
            else:
                print(f"[{timestamp}] #{iteration:4d} | Error reading GPIO state")
            
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\n\nStopped by user")
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'gpio_hvac' in globals() and gpio_hvac:
            gpio_hvac.close()
        if 'lgpio_handle' in globals() and lgpio_handle is not None:
            try:
                import lgpio
                lgpio.gpiochip_close(lgpio_handle)
            except:
                pass
        print("GPIO cleaned up")

if __name__ == '__main__':
    main()


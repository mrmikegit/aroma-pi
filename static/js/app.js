// Global variables
let statusInterval;
let historyInterval;
let hvacChart;
let swRegistration = null;
let pushSupported = 'serviceWorker' in navigator && 'PushManager' in window;
let previousOilPercentage = 100;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initializeChart();
    loadSettings();
    startStatusUpdates();
    startHistoryUpdates();
    registerServiceWorker();
});

// Initialize Chart.js for HVAC history
function initializeChart() {
    const ctx = document.getElementById('hvacChart').getContext('2d');
    
    hvacChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'HVAC Fan State',
                data: [],
                borderColor: 'rgb(102, 126, 234)',
                backgroundColor: 'rgba(102, 126, 234, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 1,
                    ticks: {
                        stepSize: 1,
                        callback: function(value) {
                            return value === 1 ? 'On' : 'Off';
                        }
                    },
                    title: {
                        display: true,
                        text: 'State'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Time'
                    },
                    ticks: {
                        maxTicksLimit: 12
                    }
                }
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return 'HVAC Fan: ' + (context.parsed.y === 1 ? 'On' : 'Off');
                        }
                    }
                }
            }
        }
    });
}

// Load settings from server
async function loadSettings() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        
        // Update UI elements
        document.getElementById('enabled').checked = data.enabled;
        document.getElementById('dutyCycle').value = data.duty_cycle;
        document.getElementById('businessHours').checked = data.business_hours_enabled;
        document.getElementById('businessStart').value = data.business_hours_start;
        document.getElementById('businessEnd').value = data.business_hours_end;
        
        // Oil settings
        document.getElementById('oilUsageRate').value = data.oil_usage_rate_ml_per_hour || 10.0;
        document.getElementById('oilBottleCapacity').value = data.oil_bottle_capacity_ml || 500.0;
        
        // Show/hide business hours times
        document.getElementById('businessHoursTimes').style.display = 
            data.business_hours_enabled ? 'block' : 'none';
        
        updateStatusDisplay(data);
    } catch (error) {
        console.error('Error loading settings:', error);
    }
}

// Update status display
function updateStatusDisplay(data) {
    // HVAC Status
    const hvacStatus = document.getElementById('hvacStatus');
    hvacStatus.textContent = data.hvac_fan_state ? 'On' : 'Off';
    hvacStatus.className = 'status-value ' + (data.hvac_fan_state ? 'on' : 'off');
    
    // Pump Status
    const pumpStatus = document.getElementById('pumpStatus');
    pumpStatus.textContent = data.pump_on ? 'On' : 'Off';
    pumpStatus.className = 'status-value ' + (data.pump_on ? 'on' : 'off');
    
    // Fan Status
    const fanStatus = document.getElementById('fanStatus');
    fanStatus.textContent = data.fan_on ? 'On' : 'Off';
    fanStatus.className = 'status-value ' + (data.fan_on ? 'on' : 'off');
    
    // System Enabled
    const systemEnabled = document.getElementById('systemEnabled');
    systemEnabled.textContent = data.enabled ? 'Enabled' : 'Disabled';
    systemEnabled.className = 'status-value ' + (data.enabled ? 'on' : 'off');
    
    // Check if oil just hit 0% and system was automatically disabled
    const currentOilPercentage = data.oil_percentage || 0;
    if (previousOilPercentage > 0 && currentOilPercentage <= 0 && !data.enabled) {
        // System was automatically disabled due to oil depletion
        alert('⚠️ Oil depleted! System has been automatically disabled. Please refill the oil bottle and reset the counters.');
    }
    previousOilPercentage = currentOilPercentage;
    
    // Runtime counters
    document.getElementById('fanRuntime').textContent = 
        data.fan_runtime_minutes.toFixed(1);
    
    // Fuel gauge
    const oilRemaining = data.oil_remaining_ml || 0;
    const oilPercentage = data.oil_percentage || 0;
    const fuelGaugeFill = document.getElementById('fuelGaugeFill');
    const oilRemainingSpan = document.getElementById('oilRemaining');
    const oilPercentageSpan = document.getElementById('oilPercentage');
    
    // Set gauge fill percentage (clamp between 0 and 100)
    const fillPercent = Math.max(0, Math.min(100, oilPercentage));
    fuelGaugeFill.style.width = fillPercent + '%';
    
    // Update color based on level
    if (fillPercent > 50) {
        fuelGaugeFill.className = 'fuel-gauge-fill high';
    } else if (fillPercent > 20) {
        fuelGaugeFill.className = 'fuel-gauge-fill medium';
    } else {
        fuelGaugeFill.className = 'fuel-gauge-fill low';
    }
    
    oilRemainingSpan.textContent = oilRemaining.toFixed(1);
    oilPercentageSpan.textContent = `(${fillPercent.toFixed(1)}%)`;
}

// Start status update polling
function startStatusUpdates() {
    updateStatus();
    statusInterval = setInterval(updateStatus, 2000); // Update every 2 seconds
}

// Update status from server
async function updateStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        updateStatusDisplay(data);
    } catch (error) {
        console.error('Error updating status:', error);
    }
}

// Start history update polling
function startHistoryUpdates() {
    updateHistory();
    historyInterval = setInterval(updateHistory, 30000); // Update every 30 seconds
}

// Update history chart
async function updateHistory() {
    try {
        const response = await fetch('/api/history');
        const history = await response.json();
        
        if (history.length === 0) return;
        
        // Sort by timestamp
        history.sort((a, b) => new Date(a[0]) - new Date(b[0]));
        
        // Prepare data for chart
        const labels = history.map(item => {
            const date = new Date(item[0]);
            return date.toLocaleTimeString('en-US', { 
                hour: '2-digit', 
                minute: '2-digit' 
            });
        });
        
        const data = history.map(item => item[1] ? 1 : 0);
        
        // Update chart
        hvacChart.data.labels = labels;
        hvacChart.data.datasets[0].data = data;
        hvacChart.update('none'); // 'none' mode for smooth updates
    } catch (error) {
        console.error('Error updating history:', error);
    }
}

// Update enabled state
async function updateEnabled() {
    const enabled = document.getElementById('enabled').checked;
    await updateSettings({ enabled });
}

// Update duty cycle
async function updateDutyCycle() {
    const dutyCycle = document.getElementById('dutyCycle').value;
    await updateSettings({ duty_cycle: dutyCycle });
}

// Update business hours
async function updateBusinessHours() {
    const enabled = document.getElementById('businessHours').checked;
    const start = document.getElementById('businessStart').value;
    const end = document.getElementById('businessEnd').value;
    
    document.getElementById('businessHoursTimes').style.display = 
        enabled ? 'block' : 'none';
    
    await updateSettings({
        business_hours_enabled: enabled,
        business_hours_start: start,
        business_hours_end: end
    });
}

// Update oil settings
async function updateOilSettings() {
    const usageRate = parseFloat(document.getElementById('oilUsageRate').value);
    const bottleCapacity = parseFloat(document.getElementById('oilBottleCapacity').value);
    
    await updateSettings({
        oil_usage_rate_ml_per_hour: usageRate,
        oil_bottle_capacity_ml: bottleCapacity
    });
}

// Update settings on server
async function updateSettings(settings) {
    try {
        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(settings)
        });
        
        const result = await response.json();
        if (result.success) {
            console.log('Settings updated successfully');
        }
    } catch (error) {
        console.error('Error updating settings:', error);
        alert('Error updating settings. Please try again.');
    }
}

// Reset runtime counters
async function resetCounters() {
    if (!confirm('Are you sure you want to reset the runtime counters?')) {
        return;
    }
    
    try {
        const response = await fetch('/api/reset_counters', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const result = await response.json();
        if (result.success) {
            updateStatus();
            alert('Runtime counters reset successfully.');
        }
    } catch (error) {
        console.error('Error resetting counters:', error);
        alert('Error resetting counters. Please try again.');
    }
}

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (statusInterval) clearInterval(statusInterval);
    if (historyInterval) clearInterval(historyInterval);
});

// --- Push Notification Helpers ---
async function registerServiceWorker() {
    if (!pushSupported) {
        console.warn('Push notifications are not supported in this browser.');
        return;
    }
    try {
        // Register from root scope
        swRegistration = await navigator.serviceWorker.register('/sw.js');
        console.log('Service worker registered with scope:', swRegistration.scope);
    } catch (error) {
        console.error('Service worker registration failed:', error);
    }
}

async function enableNotifications() {
    if (!pushSupported) {
        alert('Push notifications are not supported on this device/browser.');
        return;
    }
    if (!swRegistration) {
        console.log('Service worker not ready, registering now...');
        await registerServiceWorker();
    }
    try {
        console.log('Requesting notification permission...');
        const permission = await Notification.requestPermission();
        console.log('Permission result:', permission);
        
        if (permission !== 'granted') {
            alert('Notifications permission was not granted. Current status: ' + permission);
            return;
        }
        await subscribeUser();
    } catch (error) {
        console.error('Error enabling notifications:', error);
        alert('Failed to enable notifications: ' + error.message);
    }
}

async function subscribeUser() {
    try {
        console.log('Fetching VAPID public key...');
        const response = await fetch('/api/vapid-public-key');
        if (!response.ok) {
            throw new Error(`Failed to fetch VAPID key: ${response.statusText}`);
        }
        
        const data = await response.json();
        if (!data.publicKey) {
            throw new Error('Server did not provide a VAPID public key');
        }
        console.log('VAPID key received');
        
        const applicationServerKey = urlBase64ToUint8Array(data.publicKey);
        
        console.log('Subscribing to PushManager...');
        const subscription = await swRegistration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey
        });
        
        console.log('Subscription object created:', JSON.stringify(subscription));
        
        console.log('Sending subscription to server...');
        const subResponse = await fetch('/api/subscribe', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(subscription)
        });
        
        if (!subResponse.ok) {
            throw new Error(`Server rejected subscription: ${subResponse.statusText}`);
        }
        
        const result = await subResponse.json();
        if (result.success) {
            console.log('Server accepted subscription');
            alert('Notifications enabled successfully!');
        } else {
            throw new Error(result.error || 'Unknown server error');
        }
    } catch (error) {
        console.error('Subscription failed details:', error);
        alert('Failed to subscribe: ' + error.message);
    }
}

async function sendTestNotification() {
    try {
        const response = await fetch('/api/test_notification', {
            method: 'POST'
        });
        const result = await response.json();
        if (result.success) {
            alert('Test notification sent.');
        } else {
            throw new Error(result.error || 'Unknown error');
        }
    } catch (error) {
        console.error('Failed to send test notification:', error);
        alert('Failed to send test notification.');
    }
}

function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
}


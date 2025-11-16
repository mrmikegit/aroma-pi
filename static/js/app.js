// Global variables
let statusInterval;
let historyInterval;
let hvacChart;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initializeChart();
    loadSettings();
    startStatusUpdates();
    startHistoryUpdates();
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


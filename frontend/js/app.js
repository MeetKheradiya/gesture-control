// AuraCast AI Gesture TV Dashboard Controller Script

let ws = null;
let reconnectTimer = null;
const consoleOutput = document.getElementById("console-output");
const videoStream = document.getElementById("video-stream");
const standbyOverlay = document.getElementById("standby-overlay");
const canvas = document.getElementById("skeleton-canvas");
const ctx = canvas.getContext("2d");

// Resize canvas to match video container size
function resizeCanvas() {
    canvas.width = videoStream.clientWidth || 640;
    canvas.height = videoStream.clientHeight || 480;
}
window.addEventListener("resize", resizeCanvas);
videoStream.addEventListener("load", resizeCanvas);

// Helper to log to virtual console
function log(msg, type = "info") {
    const time = new Date().toLocaleTimeString();
    const line = document.createElement("div");
    line.className = `log-line text-${type}`;
    line.textContent = `[${time}] ${msg}`;
    consoleOutput.appendChild(line);
    consoleOutput.scrollTop = consoleOutput.scrollHeight;
}

// Clear virtual console
document.getElementById("btn-clear-console").addEventListener("click", () => {
    consoleOutput.innerHTML = "";
    log("Console cleared.", "dim");
});

// Update Status Badge
function updateConnectionBadge(connected) {
    const badge = document.getElementById("connection-status");
    const text = badge.querySelector(".status-text");
    
    if (connected) {
        badge.className = "status-badge status-online";
        text.textContent = "System Online";
    } else {
        badge.className = "status-badge status-offline";
        text.textContent = "Connecting...";
    }
}

// Connect WebSocket
function connectWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    if (ws) ws.close();
    
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
        updateConnectionBadge(true);
        log("Telemetry WebSocket connected.", "success");
        if (reconnectTimer) {
            clearInterval(reconnectTimer);
            reconnectTimer = null;
        }
        standbyOverlay.classList.add("overlay-hidden");
        videoStream.classList.remove("overlay-hidden");
    };
    
    ws.onmessage = (event) => {
        try {
            const state = JSON.parse(event.data);
            updateDashboard(state);
        } catch (e) {
            console.error("Error parsing WebSocket JSON:", e);
        }
    };
    
    ws.onclose = () => {
        updateConnectionBadge(false);
        standbyOverlay.classList.remove("overlay-hidden");
        // Don't hide video stream immediately as MJPEG stream might still reload
        if (!reconnectTimer) {
            log("WebSocket disconnected. Retrying...", "warning");
            reconnectTimer = setInterval(connectWebSocket, 3000);
        }
    };
    
    ws.onerror = (err) => {
        console.error("WS error:", err);
    };
}

// Update UI elements from WebSocket telemetry payload
function updateDashboard(state) {
    // 1. Update hand tracking HUD statistics
    const gestureLabel = document.getElementById("stat-gesture");
    const confidenceVal = document.getElementById("stat-confidence");
    const confidenceBar = document.getElementById("stat-confidence-bar");
    const commandLabel = document.getElementById("stat-command");
    
    gestureLabel.textContent = state.gesture;
    confidenceVal.textContent = `${(state.confidence * 100).toFixed(1)}%`;
    confidenceBar.style.width = `${state.confidence * 100}%`;
    commandLabel.textContent = state.last_command || "None";
    
    // Set color coding depending on confidence limit
    if (state.confidence >= 0.85) {
        gestureLabel.className = "val highlight text-success";
        confidenceBar.style.boxShadow = "0 0 8px var(--accent-green)";
    } else {
        gestureLabel.className = "val highlight";
        confidenceBar.style.boxShadow = "0 0 6px var(--accent-cyan)";
    }
    
    // 2. Draw telemetry overlay (tracking target indicator)
    drawTelemetry(state.landmarks);
    
    // 3. Handle recording overlay
    const recordingHud = document.getElementById("recording-hud");
    if (state.recording) {
        recordingHud.classList.remove("overlay-hidden");
        document.getElementById("hud-gesture-name").textContent = `RECORDING: ${state.recording}`;
        document.getElementById("hud-progress").textContent = `${state.recorded_count} / ${state.recorded_target}`;
    } else {
        recordingHud.classList.add("overlay-hidden");
    }
}

// Draw a neon circular tracking overlay on the hand center
function drawTelemetry(landmarks) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!landmarks || landmarks.length === 0) return;
    
    // Draw target cursor at hand center (approx. using Middle finger knuckle: Landmark 9)
    const centerPoint = landmarks[9];
    if (!centerPoint) return;
    
    const cx = centerPoint.x * canvas.width;
    const cy = centerPoint.y * canvas.height;
    
    // Neon Target Crosshair
    ctx.strokeStyle = "rgba(0, 242, 254, 0.4)";
    ctx.lineWidth = 1;
    
    // Draw radar circle
    ctx.beginPath();
    ctx.arc(cx, cy, 25, 0, 2 * Math.PI);
    ctx.stroke();
    
    ctx.beginPath();
    ctx.arc(cx, cy, 5, 0, 2 * Math.PI);
    ctx.fillStyle = "rgba(0, 242, 254, 0.8)";
    ctx.fill();
    
    // Outer tick lines
    ctx.beginPath();
    ctx.moveTo(cx - 35, cy);
    ctx.lineTo(cx - 15, cy);
    ctx.moveTo(cx + 15, cy);
    ctx.lineTo(cx + 35, cy);
    ctx.moveTo(cx, cy - 35);
    ctx.lineTo(cx, cy - 15);
    ctx.moveTo(cx, cy + 15);
    ctx.lineTo(cx, cy + 35);
    ctx.stroke();
    
    ctx.fillStyle = "#00f2fe";
    ctx.font = "9px JetBrains Mono";
    ctx.fillText("TRACKING LOCK", cx - 35, cy + 45);
}

// Load configurations from backend
async function fetchStatus() {
    try {
        const response = await fetch("/api/status");
        const data = await response.json();
        
        if (data.settings) {
            // Apply settings to form inputs
            document.getElementById("select-driver").value = data.settings.active_driver;
            document.getElementById("select-tv-type").value = data.settings.wifi_tv_type;
            document.getElementById("input-tv-ip").value = data.settings.wifi_tv_ip;
            document.getElementById("input-serial-port").value = data.settings.serial_port;
            document.getElementById("input-camera-index").value = data.settings.camera_index;
            
            const confThreshold = Math.round(data.settings.confidence_threshold * 100);
            document.getElementById("input-confidence-threshold").value = confThreshold;
            document.getElementById("confidence-val").textContent = `${confThreshold}%`;
            
            document.getElementById("active-driver-badge").textContent = data.settings.active_driver;
            
            toggleConditionalSettings(data.settings.active_driver);
        }
        
        // Rebuild gesture list from model manager map
        const gestureMap = data.settings.active_driver ? (await fetch("/api/status").then(r => r.json())).settings : {};
        // Actually the gesture map isn't directly returned under settings. Let's do a request to rebuild
        rebuildGestureList();
        
    } catch (e) {
        log("Error loading backend configuration: " + e.message, "danger");
    }
}

// Toggle Driver Specific Config Sections
function toggleConditionalSettings(driver) {
    document.getElementById("wifi-config").classList.add("hidden");
    document.getElementById("ir-config").classList.add("hidden");
    
    if (driver === "Wi-Fi") {
        document.getElementById("wifi-config").classList.remove("hidden");
    } else if (driver === "IR") {
        document.getElementById("ir-config").classList.remove("hidden");
    }
}

// Select driver listener
document.getElementById("select-driver").addEventListener("change", (e) => {
    toggleConditionalSettings(e.target.value);
});

// Update slider visual indicator
document.getElementById("input-confidence-threshold").addEventListener("input", (e) => {
    document.getElementById("confidence-val").textContent = `${e.target.value}%`;
});

// Apply/Save settings
document.getElementById("btn-save-settings").addEventListener("click", async () => {
    const driver = document.getElementById("select-driver").value;
    const tvType = document.getElementById("select-tv-type").value;
    const tvIp = document.getElementById("input-tv-ip").value;
    const serialPort = document.getElementById("input-serial-port").value;
    const cameraIdx = parseInt(document.getElementById("input-camera-index").value);
    const threshold = parseFloat(document.getElementById("input-confidence-threshold").value) / 100.0;
    
    const settings = {
        active_driver: driver,
        wifi_tv_type: tvType,
        wifi_tv_ip: tvIp,
        serial_port: serialPort,
        camera_index: cameraIdx,
        confidence_threshold: threshold
    };
    
    try {
        const res = await fetch("/api/settings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(settings)
        });
        const data = await res.json();
        if (data.success) {
            log("Hardware settings saved successfully.", "success");
            document.getElementById("active-driver-badge").textContent = driver;
        } else {
            log("Failed to save settings.", "danger");
        }
    } catch (e) {
        log("Error saving settings: " + e.message, "danger");
    }
});

// Virtual remote commands trigger
document.querySelectorAll(".remote-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
        const cmd = btn.getAttribute("data-cmd");
        if (!cmd) return;
        
        btn.classList.add("active");
        setTimeout(() => btn.classList.remove("active"), 200);
        
        try {
            log(`Virtual remote: triggering manual key '${cmd}'...`, "info");
            const res = await fetch("/api/command", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ command_name: cmd })
            });
            const data = await res.json();
            if (data.success) {
                log(`Manual execution: '${cmd}' SUCCESS.`, "success");
            } else {
                log(`Manual execution: '${cmd}' FAILED.`, "danger");
            }
        } catch (e) {
            log(`Manual execute error: ${e.message}`, "danger");
        }
    });
});

// Gesture training database operations
async function rebuildGestureList() {
    const list = document.getElementById("gesture-list");
    list.innerHTML = "";
    
    // Default TV gesture commands we support mapping
    const defaultGestures = [
        "Power On/Off",
        "Volume Up",
        "Volume Down",
        "Mute",
        "Channel Up",
        "Channel Down",
        "Play/Pause",
        "Home",
        "Idle"
    ];
    
    // We could pull custom classes if loaded. Let's get them from API status
    try {
        const response = await fetch("/api/status");
        const data = await response.json();
        
        // Add gesture list items
        defaultGestures.forEach(g => {
            const li = document.createElement("li");
            li.className = "gesture-item";
            
            li.innerHTML = `
                <div class="gesture-info">
                    <span class="gesture-name">${g}</span>
                    <span class="gesture-count text-dim">Active remote trigger</span>
                </div>
                <div class="gesture-actions">
                    <button class="btn-record-gesture" onclick="recordSamples('${g}')">
                        <i class="fa-solid fa-record-vinyl"></i> Record
                    </button>
                </div>
            `;
            list.appendChild(li);
        });
    } catch (e) {
        console.error("rebuild list error:", e);
    }
}

// Add Custom Gesture Name to List
document.getElementById("btn-add-gesture").addEventListener("click", () => {
    const nameInput = document.getElementById("new-gesture-name");
    const name = nameInput.value.trim();
    if (!name) return;
    
    const list = document.getElementById("gesture-list");
    const li = document.createElement("li");
    li.className = "gesture-item";
    
    li.innerHTML = `
        <div class="gesture-info">
            <span class="gesture-name">${name}</span>
            <span class="gesture-count text-dim">Custom hand gesture</span>
        </div>
        <div class="gesture-actions">
            <button class="btn-record-gesture" onclick="recordSamples('${name}')">
                <i class="fa-solid fa-record-vinyl"></i> Record
            </button>
        </div>
    `;
    list.appendChild(li);
    log(`Custom gesture label added: '${name}'`, "info");
    nameInput.value = "";
});

// Trigger sample recording
async function recordSamples(gestureName) {
    try {
        log(`Preparing to record 100 samples for '${gestureName}'...`, "info");
        log(`Position your hand in camera frame. Recording begins in 2 seconds...`, "warning");
        
        // Timeout to position hand
        setTimeout(async () => {
            log(`Recording dataset for '${gestureName}' started!`, "danger");
            const res = await fetch("/api/record", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ gesture_name: gestureName, count: 100 })
            });
            const data = await res.json();
            if (!data.success) {
                log(`Recording error: ${data.detail || "General error"}`, "danger");
            }
        }, 2000);
        
    } catch (e) {
        log("Record request failure: " + e.message, "danger");
    }
}

// Train Classifier Model
document.getElementById("btn-train-model").addEventListener("click", async () => {
    const btn = document.getElementById("btn-train-model");
    btn.innerHTML = `<i class="fa-solid fa-arrows-spin fa-spin"></i> Training...`;
    btn.disabled = true;
    
    log("Initializing neural network training workflow...", "info");
    log("Parsing coordinate dataset and compiling PyTorch model...", "info");
    
    try {
        const res = await fetch("/api/train", { method: "POST" });
        const data = await res.json();
        
        if (data.success) {
            log(`Neural network trained successfully!`, "success");
            log(`- Total Samples: ${data.samples}`, "success");
            log(`- Gesture Classes: ${data.classes}`, "success");
            log(`- Validation Accuracy: ${(data.val_accuracy * 100).toFixed(2)}%`, "success");
            log(`- Final Epoch Loss: ${data.final_loss.toFixed(6)}`, "success");
            
            // Show metrics
            const stats = document.getElementById("training-stats");
            stats.classList.remove("hidden");
            document.getElementById("model-accuracy").textContent = `${(data.val_accuracy * 100).toFixed(1)}%`;
            document.getElementById("model-samples").textContent = data.samples;
            document.getElementById("model-classes").textContent = data.classes;
            
        } else {
            log(`Training failed: ${data.error || "Dataset is too small. Please record at least 2 distinct gestures with 100 samples each."}`, "danger");
        }
    } catch (e) {
        log("Server training failure: " + e.message, "danger");
    } finally {
        btn.innerHTML = `<i class="fa-solid fa-arrows-spin"></i> Train Model`;
        btn.disabled = false;
    }
});

// Clear local training datasets
document.getElementById("btn-clear-dataset").addEventListener("click", async () => {
    if (!confirm("Are you sure you want to delete all recorded landmarks and reset the model? This cannot be undone!")) return;
    
    try {
        const res = await fetch("/api/clear", { method: "POST" });
        const data = await res.json();
        if (data.success) {
            log("Dataset and mapping files successfully deleted.", "warning");
            document.getElementById("training-stats").classList.add("hidden");
            rebuildGestureList();
        }
    } catch (e) {
        log("Clear request failed: " + e.message, "danger");
    }
});

// Initialize on page load
window.onload = () => {
    fetchStatus();
    connectWebSocket();
    setTimeout(resizeCanvas, 500); // Small timeout to ensure image width has loaded
};

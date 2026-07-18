// DeskPilot Web Dashboard Controller Script

let ws = null;
let reconnectTimer = null;
const videoStream = document.getElementById("video-stream");
const standbyOverlay = document.getElementById("standby-overlay");
const canvas = document.getElementById("skeleton-canvas");
const ctx = canvas.getContext("2d");
const selectCamera = document.getElementById("select-camera");

// Resize canvas to match video container size
function resizeCanvas() {
    canvas.width = videoStream.clientWidth || 640;
    canvas.height = videoStream.clientHeight || 480;
}
window.addEventListener("resize", resizeCanvas);
videoStream.addEventListener("load", resizeCanvas);

// Log output safety wrapper
function log(msg, type = "info") {
    console.log(`[${type.toUpperCase()}] ${msg}`);
}

// Connect WebSocket
function connectWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    if (ws) ws.close();
    
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
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
        standbyOverlay.classList.remove("overlay-hidden");
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
    const gestureLabel = document.getElementById("stat-gesture");
    const confidenceVal = document.getElementById("stat-confidence");
    const confidenceBar = document.getElementById("stat-confidence-bar");
    const commandLabel = document.getElementById("stat-command");
    
    if (gestureLabel) gestureLabel.textContent = state.gesture;
    if (confidenceVal) confidenceVal.textContent = `${(state.confidence * 100).toFixed(1)}%`;
    if (confidenceBar) confidenceBar.style.width = `${state.confidence * 100}%`;
    if (commandLabel) commandLabel.textContent = state.last_command || "None";
    
    if (state.confidence >= 0.85) {
        if (gestureLabel) gestureLabel.className = "val highlight text-success";
        if (confidenceBar) confidenceBar.style.boxShadow = "0 0 8px var(--accent-green)";
    } else {
        if (gestureLabel) gestureLabel.className = "val highlight";
        if (confidenceBar) confidenceBar.style.boxShadow = "0 0 6px var(--accent-cyan)";
    }
    
    // Draw telemetry overlay (tracking target indicator)
    drawTelemetry(state.landmarks);
}

// Draw a neon circular tracking overlay on the hand center
function drawTelemetry(landmarks) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!landmarks || landmarks.length === 0) return;
    
    // Draw target cursor at hand center (approx. Middle finger knuckle: Landmark 9)
    const centerPoint = landmarks[9];
    if (!centerPoint) return;
    
    const cx = centerPoint.x * canvas.width;
    const cy = centerPoint.y * canvas.height;
    
    ctx.strokeStyle = "rgba(0, 242, 254, 0.4)";
    ctx.lineWidth = 1.5;
    
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

// Load configurations from backend on startup
async function fetchStatus() {
    try {
        const response = await fetch("/api/status");
        const data = await response.json();
        
        if (data.settings && selectCamera) {
            // Set the dropdown to the active camera index
            selectCamera.value = data.settings.camera_index.toString();
            log(`Connected camera index is: ${data.settings.camera_index}`, "info");
        }
    } catch (e) {
        log("Error loading backend status: " + e.message, "danger");
    }
}

// Camera selector listener
if (selectCamera) {
    selectCamera.addEventListener("change", async (e) => {
        const newCameraIdx = parseInt(e.target.value);
        log(`Requesting camera change to index: ${newCameraIdx}...`, "info");
        
        try {
            const res = await fetch("/api/settings", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ camera_index: newCameraIdx })
            });
            const data = await res.json();
            if (data.success) {
                log(`Successfully changed camera index to: ${newCameraIdx}`, "success");
            } else {
                log("Failed to change camera settings.", "danger");
            }
        } catch (err) {
            log("Error updating camera settings: " + err.message, "danger");
        }
    });
}

// Initialize on page load
window.onload = () => {
    fetchStatus();
    connectWebSocket();
    setTimeout(resizeCanvas, 500); // Small timeout to ensure image width has loaded
};

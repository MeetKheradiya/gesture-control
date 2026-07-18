import os
import sys
import asyncio
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add workspace directory to path to ensure backend imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.config import config, WORKSPACE_DIR
from backend.gesture_engine import gesture_engine
from backend.tv_drivers import execute_tv_command

app = FastAPI(title="Smart TV Gesture Controller API")

# CORS middleware for testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create frontend folders if they do not exist
frontend_dir = WORKSPACE_DIR / "frontend"
(frontend_dir / "css").mkdir(parents=True, exist_ok=True)
(frontend_dir / "js").mkdir(parents=True, exist_ok=True)

# Pydantic models for request bodies
class SettingsUpdate(BaseModel):
    camera_index: int = None
    confidence_threshold: float = None
    cooldown_seconds: float = None
    active_driver: str = None
    wifi_tv_ip: str = None
    wifi_tv_type: str = None
    serial_port: str = None

class RecordRequest(BaseModel):
    gesture_name: str
    count: int = 100

class CommandRequest(BaseModel):
    command_name: str


@app.on_event("startup")
def startup_event():
    """Start camera processing on startup."""
    gesture_engine.start()


@app.on_event("shutdown")
def shutdown_event():
    """Stop camera processing on shutdown."""
    gesture_engine.stop()


# REST API endpoints
@app.get("/api/status")
def get_status():
    """Get backend status, configuration, and state."""
    state = gesture_engine.get_state()
    return {
        "status": "online" if gesture_engine.running else "offline",
        "settings": config.settings,
        "engine_state": {k: v for k, v in state.items() if k != "landmarks" and k != "recording"}
    }


@app.post("/api/settings")
def update_settings(settings: SettingsUpdate):
    """Update system settings dynamically."""
    restart_camera = False
    
    if settings.camera_index is not None and settings.camera_index != config.get("camera_index"):
        config.set("camera_index", settings.camera_index)
        restart_camera = True
        
    if settings.confidence_threshold is not None:
        config.set("confidence_threshold", settings.confidence_threshold)
        
    if settings.cooldown_seconds is not None:
        config.set("cooldown_seconds", settings.cooldown_seconds)
        
    if settings.active_driver is not None:
        config.set("active_driver", settings.active_driver)
        
    if settings.wifi_tv_ip is not None:
        config.set("wifi_tv_ip", settings.wifi_tv_ip)
        
    if settings.wifi_tv_type is not None:
        config.set("wifi_tv_type", settings.wifi_tv_type)
        
    if settings.serial_port is not None:
        config.set("serial_port", settings.serial_port)
        
    if restart_camera and gesture_engine.running:
        print("[App] Restarting gesture engine to apply camera change...")
        gesture_engine.stop()
        gesture_engine.start()
        
    return {"success": True, "settings": config.settings}


@app.post("/api/record")
def record_gesture(req: RecordRequest):
    """Triggers landmark collection for training a gesture."""
    if not gesture_engine.running:
        raise HTTPException(status_code=400, detail="Gesture engine is offline.")
    gesture_engine.start_recording(req.gesture_name, req.count)
    return {"success": True, "message": f"Started recording {req.count} samples for '{req.gesture_name}'"}


@app.post("/api/train")
def train_model():
    """Retrains the neural network model on the CSV dataset."""
    result = gesture_engine.model_manager.train_model()
    if result["success"]:
        # Reload model weights in current manager
        gesture_engine.model_manager.load_model()
    return result


@app.post("/api/clear")
def clear_dataset():
    """Resets model training data."""
    return gesture_engine.model_manager.clear_dataset()


@app.post("/api/command")
def manual_command(req: CommandRequest):
    """Sends a TV command directly (manual trigger)."""
    success = execute_tv_command(req.command_name)
    if success:
        gesture_engine.last_command_executed = f"Manual: {req.command_name} at {time.strftime('%H:%M:%S')}" if 'time' in globals() else f"Manual: {req.command_name}"
        return {"success": True}
    else:
        return {"success": False, "error": "Failed to send command."}


# Video frame generator
def frame_generator():
    """Yields camera JPEG frames as multipart stream."""
    while True:
        frame = gesture_engine.get_latest_frame()
        if frame is not None:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        # Rate limit to ~30 FPS to save bandwidth
        time_to_sleep = 0.033
        import time
        time.sleep(time_to_sleep)


@app.get("/video_feed")
def get_video_feed():
    """Stream camera video feed inside Web UI."""
    return StreamingResponse(frame_generator(), media_type="multipart/x-mixed-replace; boundary=frame")


# WebSocket connection for telemetry/landmark streaming
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("[WebSocket] Client connected.")
    try:
        while True:
            # Check engine state
            state = gesture_engine.get_state()
            await websocket.send_json(state)
            # Send updates at ~25-30 FPS
            await asyncio.sleep(0.04)
    except WebSocketDisconnect:
        print("[WebSocket] Client disconnected.")
    except Exception as e:
        print(f"[WebSocket] Error: {e}")


# Static files routing
@app.get("/")
def get_index():
    index_file = frontend_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "Frontend index.html not found. Please create it."}

# Mount css and js subdirectories
app.mount("/css", StaticFiles(directory=str(frontend_dir / "css")), name="css")
app.mount("/js", StaticFiles(directory=str(frontend_dir / "js")), name="js")


if __name__ == "__main__":
    # Start web server on host 0.0.0.0, port 8000
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)

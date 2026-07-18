import time
import cv2
import sys
import requests
import mediapipe as mp
from mediapipe.tasks import python as mp_tasks
from mediapipe.tasks.python import vision as mp_vision
import threading
from backend.config import config, DATA_DIR
from backend.model import GestureModelManager
from backend.tv_drivers import execute_tv_command

MODEL_TASK_PATH = DATA_DIR / "hand_landmarker.task"
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"

def download_model_if_needed():
    if not MODEL_TASK_PATH.exists():
        print(f"Downloading MediaPipe Hand Landmarker model from {MODEL_URL}...")
        try:
            r = requests.get(MODEL_URL, stream=True, timeout=20)
            r.raise_for_status()
            with open(MODEL_TASK_PATH, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            print("Download completed successfully.")
        except Exception as e:
            print(f"Error downloading MediaPipe model: {e}")

class GestureEngine:
    def __init__(self):
        self.model_manager = GestureModelManager()
        self.detector = None
        
        # State variables
        self.running = False
        self.camera = None
        self.latest_frame = None
        self.latest_prediction = "None"
        self.latest_confidence = 0.0
        self.last_command_executed = "None"
        self.last_command_time = 0.0
        self.active_landmarks = []  # Current 21 landmarks
        
        # Dynamic training state
        self.recording_gesture = None
        self.recorded_samples_count = 0
        self.samples_to_record = 100
        
        # Gesture smoothing
        self.gesture_buffer = []
        self.buffer_size = 5
        
        # Thread safety
        self.lock = threading.Lock()
        self.thread = None

    def initialize_mediapipe(self):
        """Initializes MediaPipe HandLandmarker context using settings."""
        download_model_if_needed()
        if not MODEL_TASK_PATH.exists():
            raise FileNotFoundError("MediaPipe HandLandmarker model file missing.")
            
        base_options = mp_tasks.BaseOptions(model_asset_path=str(MODEL_TASK_PATH))
        options = mp_vision.HandLandmarkerOptions(
            base_options=base_options,
            num_hands=config.get("max_num_hands", 1),
            min_hand_detection_confidence=config.get("min_detection_confidence", 0.7),
            min_hand_presence_confidence=config.get("min_tracking_confidence", 0.7),
            running_mode=mp_vision.RunningMode.IMAGE
        )
        self.detector = mp_vision.HandLandmarker.create_from_options(options)

    def start(self):
        """Starts the camera acquisition and processing thread."""
        with self.lock:
            if self.running:
                return
            self.running = True
            
        self.initialize_mediapipe()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        print("Gesture engine thread started.")

    def stop(self):
        """Stops the camera thread."""
        with self.lock:
            self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        if self.camera:
            self.camera.release()
            self.camera = None
        if self.detector:
            try:
                self.detector.close()
            except Exception:
                pass
            self.detector = None
        print("Gesture engine stopped.")

    def start_recording(self, gesture_name, count=100):
        """Triggers sample recording for a specific gesture name."""
        with self.lock:
            self.recording_gesture = gesture_name
            self.recorded_samples_count = 0
            self.samples_to_record = count
        print(f"Started recording {count} samples for gesture: '{gesture_name}'")

    def stop_recording(self):
        """Forces stop of recording."""
        with self.lock:
            self.recording_gesture = None
        print("Recording stopped manually.")

    def _draw_neon_skeleton(self, frame, landmarks_list, width, height):
        """
        Draws a beautiful neon cyan/purple glowing skeleton on the hand.
        landmarks_list: list of 21 landmark objects.
        """
        # Connection pairs (MediaPipe Hands connections)
        connections = [
            # Thumb
            (0, 1), (1, 2), (2, 3), (3, 4),
            # Index
            (0, 5), (5, 6), (6, 7), (7, 8),
            # Middle
            (9, 10), (10, 11), (11, 12),
            # Ring
            (13, 14), (14, 15), (15, 16),
            # Pinky
            (0, 17), (17, 18), (18, 19), (19, 20),
            # Palm connections
            (5, 9), (9, 13), (13, 17)
        ]
        
        # Get absolute pixel coordinates
        pts = {}
        for idx, lm in enumerate(landmarks_list):
            cx, cy = int(lm.x * width), int(lm.y * height)
            pts[idx] = (cx, cy)
            
        # Draw skeleton connections (glowing neon cyan lines)
        for start, end in connections:
            if start in pts and end in pts:
                # Double draw for glow effect
                cv2.line(frame, pts[start], pts[end], (255, 0, 150), 3) # Purple Outer glow
                cv2.line(frame, pts[start], pts[end], (255, 255, 0), 1) # Cyan Inner line
                
        # Draw joints (glowing neon pink dots)
        for idx, pt in pts.items():
            # Highlight index tip, thumb tip, middle tip, etc.
            if idx in [4, 8, 12, 16, 20]:
                cv2.circle(frame, pt, 7, (0, 0, 255), -1)      # Outer Red
                cv2.circle(frame, pt, 4, (0, 255, 255), -1)    # Inner Yellow
            else:
                cv2.circle(frame, pt, 5, (255, 0, 255), -1)    # Magenta outer
                cv2.circle(frame, pt, 2, (255, 255, 255), -1)  # White center

    def _process_prediction(self, gesture_name, confidence):
        """
        Applies smoothing to gesture predictions and triggers TV actions
        if validation thresholds are met and cooldown is inactive.
        """
        if gesture_name == "Unknown" or confidence < config.get("confidence_threshold", 0.85):
            self.gesture_buffer.clear()
            return
            
        # Strict physical heuristic validation to prevent random hand shape false positives
        landmarks = self.active_landmarks
        if landmarks and len(landmarks) >= 21:
            def get_dist(p1, p2):
                return ((p1['x'] - p2['x'])**2 + (p1['y'] - p2['y'])**2 + (p1['z'] - p2['z'])**2)**0.5
                
            wrist = landmarks[0]
            
            # Extension state relative to wrist: straight (>1.10) vs curled (<0.9)
            index_ext = get_dist(landmarks[8], wrist) > get_dist(landmarks[6], wrist) * 1.10
            middle_ext = get_dist(landmarks[12], wrist) > get_dist(landmarks[10], wrist) * 1.10
            ring_ext = get_dist(landmarks[16], wrist) > get_dist(landmarks[14], wrist) * 1.10
            pinky_ext = get_dist(landmarks[20], wrist) > get_dist(landmarks[18], wrist) * 1.10
            
            is_valid = True
            
            if gesture_name in ["Volume Up", "Volume Down"]:
                # Volume actions (Thumbs Up/Down) strictly require:
                # 1. The thumb to be extended (dist from tip 4 to wrist > dist from joint 2 to wrist)
                # 2. All 4 other fingers curled
                thumb_ext = get_dist(landmarks[4], wrist) > get_dist(landmarks[2], wrist) * 1.10
                if not thumb_ext or index_ext or middle_ext or ring_ext or pinky_ext:
                    is_valid = False
            elif gesture_name in ["Previous", "Next"]:
                # Prev/Next (Two Fingers) strictly requires Index and Middle extended, and Ring/Pinky curled
                if not index_ext or not middle_ext or ring_ext or pinky_ext:
                    is_valid = False
            elif gesture_name == "Play/Pause":
                # Play/Pause (Raised Hand/Open Palm) strictly requires all fingers extended
                if not index_ext or not middle_ext or not ring_ext or not pinky_ext:
                    is_valid = False
            elif gesture_name in ["Fast Forward", "Rewind"]:
                # Fast Forward / Rewind (Pinch) strictly require Thumb and Index tips touching
                p4 = landmarks[4]
                p8 = landmarks[8]
                p5 = landmarks[5]
                p17 = landmarks[17]
                dist_pinch = get_dist(p4, p8)
                dist_palm = get_dist(p5, p17)
                if dist_palm == 0 or dist_pinch >= dist_palm * 0.35:
                    is_valid = False
                    
            if not is_valid:
                # Discard predictions violating geometric criteria
                self.gesture_buffer.clear()
                return
            
        # Add to rolling buffer for smoothing
        self.gesture_buffer.append(gesture_name)
        if len(self.gesture_buffer) > self.buffer_size:
            self.gesture_buffer.pop(0)
            
        # Check if the buffer is uniform (all elements are the same gesture)
        if len(self.gesture_buffer) == self.buffer_size and len(set(self.gesture_buffer)) == 1:
            current_time = time.time()
            
            # Dynamic cooldown: Volume changes adjust rapidly, while other actions hold standard cooldowns
            if gesture_name in ["Volume Up", "Volume Down", "Fast Forward", "Rewind"]:
                cooldown = 0.15  # rapid repeat speed for seekbar and volume
            else:
                cooldown = 1.2   # Safety delay for toggle commands
            
            # Trigger TV command
            if current_time - self.last_command_time > cooldown:
                # Avoid triggering 'Unknown' or idle gestures if mapped
                if gesture_name not in ["Idle", "Background", "Unknown"]:
                    print(f"[Engine] Gesture '{gesture_name}' stable. Executing TV command...")
                    success = execute_tv_command(gesture_name)
                    if success:
                        self.last_command_executed = f"{gesture_name} at {time.strftime('%H:%M:%S')}"
                    else:
                        self.last_command_executed = f"Failed: {gesture_name}"
                    self.last_command_time = current_time
                    
                    # Only clear buffer for toggle commands, allowing volume and seekbar commands to fire continuously
                    if gesture_name not in ["Volume Up", "Volume Down", "Fast Forward", "Rewind"]:
                        self.gesture_buffer.clear()

    def _run(self):
        """Internal processing loop run inside thread."""
        cam_idx = config.get("camera_index", 0)
        width = config.get("frame_width", 640)
        height = config.get("frame_height", 480)
        flip = config.get("flip_camera", True)
        
        # Open camera. On Windows, DSHOW backend is faster and less prone to locks
        if sys.platform.startswith("win"):
            self.camera = cv2.VideoCapture(cam_idx, cv2.CAP_DSHOW)
        else:
            self.camera = cv2.VideoCapture(cam_idx)
            
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        
        if not self.camera.isOpened():
            print(f"Error: Could not open camera source {cam_idx}")
            with self.lock:
                self.running = False
            return
            
        print("Camera successfully opened.")
        
        while True:
            # Check running state
            with self.lock:
                if not self.running:
                    break
                    
            ret, frame = self.camera.read()
            if not ret:
                time.sleep(0.01)
                continue
                
            # Flip camera for intuitive mirror view
            if flip:
                frame = cv2.flip(frame, 1)
                
            # RGB conversion for MediaPipe Tasks
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            results = self.detector.detect(mp_image)
            
            gesture_name = "Unknown"
            confidence = 0.0
            landmarks_detected = False
            raw_landmarks = []
            
            if results.hand_landmarks:
                landmarks_detected = True
                # Get the first hand detected
                hand_landmarks = results.hand_landmarks[0]
                
                # Format landmarks into basic list of dicts for frontend / utils
                for lm in hand_landmarks:
                    raw_landmarks.append({"x": lm.x, "y": lm.y, "z": lm.z})
                    
                self.active_landmarks = raw_landmarks
                
                # Draw neon skeleton overlay on frame
                self._draw_neon_skeleton(frame, hand_landmarks, frame.shape[1], frame.shape[0])
                
                # Perform dynamic actions: Recording vs. Classification
                with self.lock:
                    recording_active = self.recording_gesture is not None
                    current_recording_gesture = self.recording_gesture
                    
                if recording_active:
                    # Save sample
                    sample_lms = [[lm.x, lm.y, lm.z] for lm in hand_landmarks]
                    self.model_manager.record_sample(current_recording_gesture, sample_lms)
                    self.recorded_samples_count += 1
                    
                    # Overlay recording text
                    cv2.putText(frame, f"RECORDING '{current_recording_gesture}': {self.recorded_samples_count}/{self.samples_to_record}", 
                                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                                
                    if self.recorded_samples_count >= self.samples_to_record:
                        with self.lock:
                            self.recording_gesture = None
                        print(f"Finished recording dataset for {current_recording_gesture}")
                else:
                    # Normal Mode: Predict gesture
                    sample_lms = [[lm.x, lm.y, lm.z] for lm in hand_landmarks]
                    gesture_name, confidence = self.model_manager.predict(sample_lms)
                    
                    # Intercept and override if the hand is in a Pinch state
                    is_pinching = False
                    try:
                        p4 = raw_landmarks[4]
                        p8 = raw_landmarks[8]
                        p5 = raw_landmarks[5]
                        p17 = raw_landmarks[17]
                        dist_pinch = ((p4['x'] - p8['x'])**2 + (p4['y'] - p8['y'])**2 + (p4['z'] - p8['z'])**2)**0.5
                        dist_palm = ((p5['x'] - p17['x'])**2 + (p5['y'] - p17['y'])**2 + (p5['z'] - p17['z'])**2)**0.5
                        if dist_palm > 0 and dist_pinch < dist_palm * 0.35:
                            is_pinching = True
                    except Exception:
                        pass
                        
                    if is_pinching:
                        try:
                            import math
                            p0 = raw_landmarks[0]
                            p9 = raw_landmarks[9]
                            dx = p9['x'] - p0['x']
                            dy = p9['y'] - p0['y']
                            angle_deg = math.degrees(math.atan2(dy, dx))
                            tilt = angle_deg + 90
                            if tilt > 180: tilt -= 360
                            elif tilt < -180: tilt += 360
                            
                            # If tilted right by more than 28 degrees -> Fast Forward
                            if tilt > 28:
                                gesture_name = "Fast Forward"
                                confidence = 0.99
                            # If tilted left by more than 28 degrees -> Rewind
                            elif tilt < -28:
                                gesture_name = "Rewind"
                                confidence = 0.99
                            else:
                                gesture_name = "Idle"
                                confidence = 0.99
                        except Exception as te:
                            print(f"[Engine] Pinch tilt calculation error: {te}")
                    
                    self.latest_prediction = gesture_name
                    self.latest_confidence = confidence
                    
                    # Apply prediction smoothing and send remote controls
                    self._process_prediction(gesture_name, confidence)
                    
                    # Overlay classification stats on frame
                    hud_color = (0, 255, 0) if confidence >= config.get("confidence_threshold", 0.85) else (0, 165, 255)
                    cv2.putText(frame, f"Gesture: {gesture_name} ({confidence*100:.1f}%)", 
                                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, hud_color, 2)
            else:
                self.active_landmarks = []
                self.latest_prediction = "None"
                self.latest_confidence = 0.0
                
            # Draw TV controller HUD info
            driver_name = config.get("active_driver", "Local")
            cv2.putText(frame, f"Driver: {driver_name} | Last Cmd: {self.last_command_executed}", 
                        (10, frame.shape[0] - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                        
            # Compress the frame to JPEG for web streaming
            ret, jpeg = cv2.imencode('.jpg', frame)
            if ret:
                self.latest_frame = jpeg.tobytes()
                
            # Sleep slightly to prevent high CPU utilization
            time.sleep(0.01)

    def get_latest_frame(self):
        """Returns the latest processed JPEG frame."""
        return self.latest_frame

    def get_state(self):
        """Returns the current state dictionary for API / Websocket reporting."""
        with self.lock:
            recording_gesture = self.recording_gesture
            
        return {
            "gesture": self.latest_prediction,
            "confidence": self.latest_confidence,
            "last_command": self.last_command_executed,
            "landmarks": self.active_landmarks,
            "recording": recording_gesture,
            "recorded_count": self.recorded_samples_count,
            "recorded_target": self.samples_to_record,
            "driver": config.get("active_driver"),
            "wifi_tv_ip": config.get("wifi_tv_ip"),
            "wifi_tv_type": config.get("wifi_tv_type"),
            "serial_port": config.get("serial_port")
        }

# Global engine instance
gesture_engine = GestureEngine()

import time
import cv2
import sys
import numpy as np
from PySide6.QtCore import QThread, Signal, Qt, QSize
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QProgressBar
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QPen, QFont
import mediapipe as mp
from mediapipe.tasks import python as mp_tasks
from mediapipe.tasks.python import vision as mp_vision

from backend.config import config, DATA_DIR
from backend.model import GestureModelManager
from backend.tv_drivers import execute_tv_command
from backend.face_auth import FaceAuthenticator
from backend.gesture_engine import download_model_if_needed, MODEL_TASK_PATH

class CameraThread(QThread):
    """
    QThread running the OpenCV frame capture, face authentication,
    MediaPipe hands detection, PyTorch inference, and HUD rendering.
    """
    frame_ready = Signal(QImage)
    telemetry_ready = Signal(dict)
    log_emitted = Signal(str, str) # message, level

    def __init__(self):
        super().__init__()
        self.running = False
        self.model_manager = GestureModelManager()
        self.face_auth = FaceAuthenticator()
        self.detector = None
        self.camera = None
        
        # Recording training dataset state
        self.recording_gesture = None
        self.recorded_samples = []
        self.recorded_target = 100
        
        # Face profiling mode
        self.profiling_face = False
        self.profiled_chips = []
        self.profile_target = 30
        
        # Prediction smoothing
        self.gesture_buffer = []
        self.buffer_size = 5
        self.last_command_time = 0.0
        self.last_command_executed = "None"

    def start_recording(self, gesture_name, count=100):
        self.recording_gesture = gesture_name
        self.recorded_samples = []
        self.recorded_target = count

    def start_face_profiling(self, count=30):
        self.profiled_chips = []
        self.profile_target = count
        self.profiling_face = True

    def initialize_detector(self):
        download_model_if_needed()
        if not MODEL_TASK_PATH.exists():
            self.log_emitted.emit("MediaPipe HandLandmarker task model missing.", "danger")
            return False
            
        base_options = mp_tasks.BaseOptions(model_asset_path=str(MODEL_TASK_PATH))
        options = mp_vision.HandLandmarkerOptions(
            base_options=base_options,
            num_hands=config.get("max_num_hands", 1),
            min_hand_detection_confidence=config.get("min_detection_confidence", 0.7),
            min_hand_presence_confidence=config.get("min_tracking_confidence", 0.7),
            running_mode=mp_vision.RunningMode.IMAGE
        )
        self.detector = mp_vision.HandLandmarker.create_from_options(options)
        return True

    def run(self):
        self.running = True
        if not self.initialize_detector():
            self.running = False
            return
            
        cam_idx = config.get("camera_index", 0)
        width = config.get("frame_width", 640)
        height = config.get("frame_height", 480)
        flip = config.get("flip_camera", True)
        
        if sys.platform.startswith("win"):
            self.camera = cv2.VideoCapture(cam_idx, cv2.CAP_DSHOW)
        else:
            self.camera = cv2.VideoCapture(cam_idx)
            
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        
        if not self.camera.isOpened():
            self.log_emitted.emit(f"Could not open camera index {cam_idx}", "danger")
            self.running = False
            return
            
        self.log_emitted.emit(f"Camera index {cam_idx} active.", "success")
        
        # Load facial profile status
        face_lockout_enabled = config.get("face_lockout_enabled", False)
        
        while self.running:
            ret, frame = self.camera.read()
            if not ret:
                time.sleep(0.01)
                continue
                
            if flip:
                frame = cv2.flip(frame, 1)
                
            h_h, h_w = frame.shape[:2]
            
            # 1. USER AUTHENTICATION (Optional Face Recognition)
            is_unlocked = True
            face_status_text = "Unlocked"
            face_bbox = None
            
            if face_lockout_enabled or self.profiling_face:
                is_unlocked, face_status_text, auth_conf, face_bbox = self.face_auth.authenticate(frame)
                
                # Overrule lock status if facial profile is not configured yet
                if not self.face_auth.is_configured() and not self.profiling_face:
                    is_unlocked = True
                    face_status_text = "No facial profile configured."
                    
                # Handle Face Profiling / Registration collection
                if self.profiling_face and face_bbox:
                    chip = self.face_auth.capture_training_samples(frame)
                    if chip is not None:
                        self.profiled_chips.append(chip)
                        # HUD Indicator
                        cv2.putText(frame, f"REGISTERING FACE: {len(self.profiled_chips)}/{self.profile_target}", 
                                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)
                                    
                        if len(self.profiled_chips) >= self.profile_target:
                            self.profiling_face = False
                            success = self.face_auth.train_profile(self.profiled_chips)
                            if success:
                                self.log_emitted.emit("Facial profile trained and written to settings.", "success")
                            else:
                                self.log_emitted.emit("Facial profile training failed.", "danger")
                                
                # Render Face Border
                if face_bbox:
                    fx, fy, fw, fh = face_bbox
                    border_color = (0, 255, 0) if is_unlocked else (0, 0, 255)
                    cv2.rectangle(frame, (fx, fy), (fx+fw, fy+fh), border_color, 2)
                    cv2.putText(frame, face_status_text, (fx, fy-10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, border_color, 1)
                                
            # 2. HAND GESTURE RECOGNITION (Only if unlocked by face auth)
            gesture_name = "Locked" if not is_unlocked else "Unknown"
            confidence = 0.0
            raw_lms = []
            
            if is_unlocked and not self.profiling_face:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
                results = self.detector.detect(mp_image)
                
                if results.hand_landmarks:
                    hand_landmarks = results.hand_landmarks[0]
                    
                    # Convert to raw landmark dicts for signal
                    for lm in hand_landmarks:
                        raw_lms.append({"x": lm.x, "y": lm.y, "z": lm.z})
                        
                    # Custom Vector Skeleton Drawing
                    self._draw_skeleton(frame, hand_landmarks)
                    
                    # Normal / Recording actions
                    sample_lms = [[lm.x, lm.y, lm.z] for lm in hand_landmarks]
                    
                    if self.recording_gesture:
                        self.model_manager.record_sample(self.recording_gesture, sample_lms)
                        self.recorded_samples.append(sample_lms)
                        
                        # HUD Text
                        cv2.putText(frame, f"RECORDING '{self.recording_gesture}': {len(self.recorded_samples)}/{self.recorded_target}", 
                                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                                    
                        if len(self.recorded_samples) >= self.recorded_target:
                            self.log_emitted.emit(f"Finished dataset collection for gesture: '{self.recording_gesture}'", "success")
                            self.recording_gesture = None
                    else:
                        # Classification
                        gesture_name, confidence = self.model_manager.predict(sample_lms)
                        self._process_prediction(gesture_name, confidence)
                        
                        # Draw stats HUD
                        hud_color = (0, 255, 0) if confidence >= config.get("confidence_threshold", 0.85) else (0, 165, 255)
                        cv2.putText(frame, f"Pose: {gesture_name} ({confidence*100:.1f}%)", 
                                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, hud_color, 2)
            elif not is_unlocked:
                # Lockout Overlay Icon
                cv2.rectangle(frame, (0, 0), (width, height), (0, 0, 0), -1)
                cv2.putText(frame, "SYSTEM LOCKED - Face Authentication Required", 
                            (int(width/2) - 220, int(height/2)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                            
            # Convert frame back to PySide6 QImage
            rgb_render = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            q_image = QImage(rgb_render.data, rgb_render.shape[1], rgb_render.shape[0], 
                             rgb_render.strides[0], QImage.Format_RGB888)
            
            # Emit frames & telemetry data
            self.frame_ready.emit(q_image)
            self.telemetry_ready.emit({
                "gesture": gesture_name,
                "confidence": confidence,
                "landmarks": raw_lms,
                "last_command": self.last_command_executed,
                "is_unlocked": is_unlocked
            })
            
            # Restrict frame rates slightly to keep CPU usage optimized (~30 FPS)
            time.sleep(0.03)
            
        # Cleanup
        if self.camera:
            self.camera.release()
        if self.detector:
            self.detector.close()

    def _draw_skeleton(self, frame, landmarks):
        """Draw neon glowing joints and connectors on frame."""
        connections = [
            (0, 1), (1, 2), (2, 3), (3, 4),
            (0, 5), (5, 6), (6, 7), (7, 8),
            (9, 10), (10, 11), (11, 12),
            (13, 14), (14, 15), (15, 16),
            (0, 17), (17, 18), (18, 19), (19, 20),
            (5, 9), (9, 13), (13, 17)
        ]
        h, w = frame.shape[:2]
        pts = {}
        for idx, lm in enumerate(landmarks):
            pts[idx] = (int(lm.x * w), int(lm.y * h))
            
        for start, end in connections:
            if start in pts and end in pts:
                cv2.line(frame, pts[start], pts[end], (255, 0, 150), 3) # Glow
                cv2.line(frame, pts[start], pts[end], (255, 255, 0), 1)
                
        for idx, pt in pts.items():
            if idx in [4, 8, 12, 16, 20]:
                cv2.circle(frame, pt, 6, (0, 0, 255), -1)
                cv2.circle(frame, pt, 3, (0, 255, 255), -1)
            else:
                cv2.circle(frame, pt, 4, (255, 0, 255), -1)

    def _process_prediction(self, gesture_name, confidence):
        if gesture_name == "Unknown" or confidence < config.get("confidence_threshold", 0.85):
            self.gesture_buffer.clear()
            return
            
        self.gesture_buffer.append(gesture_name)
        if len(self.gesture_buffer) > self.buffer_size:
            self.gesture_buffer.pop(0)
            
        if len(self.gesture_buffer) == self.buffer_size and len(set(self.gesture_buffer)) == 1:
            curr_time = time.time()
            cooldown = config.get("cooldown_seconds", 1.5)
            
            if curr_time - self.last_command_time > cooldown:
                if gesture_name not in ["Idle", "Background", "Unknown"]:
                    self.log_emitted.emit(f"Stable gesture '{gesture_name}' recognized. Executing remote key...", "success")
                    success = execute_tv_command(gesture_name)
                    if success:
                        self.last_command_executed = f"{gesture_name} at {time.strftime('%H:%M:%S')}"
                    else:
                        self.last_command_executed = f"Failed: {gesture_name}"
                    self.last_command_time = curr_time
                    self.gesture_buffer.clear()

    def stop(self):
        self.running = False
        self.wait()


class CameraWidget(QWidget):
    """
    GUI Widget wrapping the live camera preview, skeleton overlays,
    and confidence feedback.
    """
    def __init__(self, thread: CameraThread):
        super().__init__()
        self.thread = thread
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Display Screen Box
        self.screen_label = QLabel("Initializing camera module...")
        self.screen_label.setAlignment(Qt.AlignCenter)
        self.screen_label.setMinimumSize(QSize(480, 360))
        self.screen_label.setStyleSheet("background-color: #050508; border-radius: 8px; border: 1px solid #1f2833;")
        layout.addWidget(self.screen_label)
        
        # HUD Panel (Confidence, Gesture Name, Commands)
        hud_layout = QHBoxLayout()
        
        self.gesture_label = QLabel("Gesture: None")
        self.gesture_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #00f2fe;")
        
        self.conf_bar = QProgressBar()
        self.conf_bar.setRange(0, 100)
        self.conf_bar.setValue(0)
        self.conf_bar.setFixedHeight(12)
        
        self.command_label = QLabel("Last Command: None")
        self.command_label.setStyleSheet("font-size: 12px; color: #9ca3af;")
        
        hud_layout.addWidget(self.gesture_label, 1)
        hud_layout.addWidget(self.conf_bar, 2)
        hud_layout.addWidget(self.command_label, 1)
        
        layout.addLayout(hud_layout)
        
        # Connect Thread signals
        self.thread.frame_ready.connect(self.update_frame)
        self.thread.telemetry_ready.connect(self.update_telemetry)

    def update_frame(self, q_image):
        scaled = q_image.scaled(self.screen_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.screen_label.setPixmap(QPixmap.fromImage(scaled))

    def update_telemetry(self, data):
        self.gesture_label.setText(f"Gesture: {data['gesture']}")
        self.conf_bar.setValue(int(data["confidence"] * 100))
        self.command_label.setText(f"Last Command: {data['last_command']}")

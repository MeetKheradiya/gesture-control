import os
import cv2
import numpy as np
from pathlib import Path
from backend.config import DATA_DIR

FACES_DIR = DATA_DIR / "faces"
FACES_DIR.mkdir(parents=True, exist_ok=True)
MODEL_FACE_PATH = str(FACES_DIR / "face_model.xml")

class FaceAuthenticator:
    """
    Handles local private face recognition user authentication.
    Uses Haar Cascades for face detection and LBPH (Local Binary Patterns Histograms)
    for face verification, ensuring lightweight, offline execution on Pi & Windows.
    """
    def __init__(self):
        self.cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        self.face_cascade = cv2.CascadeClassifier(self.cascade_path)
        
        # Check if opencv-contrib face module is available
        self.recognizer = None
        try:
            self.recognizer = cv2.face.LBPHFaceRecognizer_create()
            self.has_face_module = True
        except AttributeError:
            print("[FaceAuth] OpenCV face module (LBPH) not available. Falling back to simple face detection lockout.")
            self.has_face_module = False
            
        self.trained = False
        self.load_model()

    def load_model(self):
        if self.has_face_module and os.path.exists(MODEL_FACE_PATH):
            try:
                self.recognizer.read(MODEL_FACE_PATH)
                self.trained = True
                print("[FaceAuth] Facial authentication model loaded.")
            except Exception as e:
                print(f"[FaceAuth] Error loading model: {e}")
                self.trained = False

    def is_configured(self):
        """Returns True if there is a trained profile on disk."""
        return self.trained if self.has_face_module else False

    def capture_training_samples(self, frame) -> np.ndarray:
        """
        Detects a face in the frame, crops it, converts to grayscale, and resizes.
        Returns the processed face chip or None.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
        
        if len(faces) > 0:
            x, y, w, h = faces[0]
            face_chip = gray[y:y+h, x:x+w]
            face_chip = cv2.resize(face_chip, (200, 200))
            return face_chip
        return None

    def train_profile(self, face_chips) -> bool:
        """
        Trains the LBPH recognizer on collected gray face chips.
        Expects a list of 200x200 numpy arrays.
        """
        if not self.has_face_module or not face_chips:
            return False
            
        try:
            # We train with label '1' (Authorized User)
            labels = np.array([1] * len(face_chips), dtype=np.int32)
            self.recognizer.train(face_chips, labels)
            self.recognizer.write(MODEL_FACE_PATH)
            self.trained = True
            print(f"[FaceAuth] Successfully trained face profile with {len(face_chips)} frames.")
            return True
        except Exception as e:
            print(f"[FaceAuth] Error training model: {e}")
            return False

    def authenticate(self, frame):
        """
        Runs face recognition on the frame.
        Returns: (authenticated: bool, label_text: str, confidence_score: float, bbox: tuple)
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
        
        if len(faces) == 0:
            return False, "No Face Detected", 0.0, None
            
        x, y, w, h = faces[0]
        bbox = (x, y, w, h)
        
        # If face recognition is not trained, fall back to basic face presence check
        if not self.has_face_module or not self.trained:
            # Basic presence is treated as unlocked if profile not configured
            return True, "Unlocked (Detection)", 100.0, bbox
            
        try:
            face_chip = gray[y:y+h, x:x+w]
            face_chip = cv2.resize(face_chip, (200, 200))
            
            label_idx, confidence = self.recognizer.predict(face_chip)
            
            # LBPH confidence score is actually distance (lower is better)
            # Distance < 80 is considered a good match for LBPH
            if label_idx == 1 and confidence < 85.0:
                # Convert distance metric to a percentage (0% to 100%)
                percentage = max(0.0, min(100.0, 100.0 - (confidence / 1.5)))
                return True, "Authorized User", percentage, bbox
            else:
                percentage = max(0.0, min(100.0, 100.0 - (confidence / 1.5)))
                return False, "Unauthorized Face", percentage, bbox
        except Exception as e:
            print(f"[FaceAuth] Authentication error: {e}")
            return False, f"Auth Error: {e}", 0.0, bbox

    def clear_profile(self):
        if os.path.exists(MODEL_FACE_PATH):
            try:
                os.remove(MODEL_FACE_PATH)
            except Exception:
                pass
        self.trained = False
        print("[FaceAuth] Facial profile cleared.")

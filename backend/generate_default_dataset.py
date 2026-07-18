import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import csv
import numpy as np
import torch
from backend.config import DATA_DIR
from backend.model import normalize_landmarks, GestureModelManager, CSV_DATA_PATH, MAP_PATH

def generate_base_gestures():
    # 21 points, 3 coords
    # 0: wrist
    # 1-4: thumb
    # 5-8: index
    # 9-12: middle
    # 13-16: ring
    # 17-20: pinky
    
    gestures = {}
    
    # 1. Closed Fist (Curled fingers) -> Helper template
    fist = np.zeros((21, 3))
    fist[0] = [0.0, 0.0, 0.0]
    # Thumb curled
    fist[1] = [0.05, -0.05, -0.02]
    fist[2] = [0.08, -0.08, -0.04]
    fist[3] = [0.06, -0.10, -0.05]
    fist[4] = [0.04, -0.08, -0.05]
    # Index curled
    fist[5] = [0.08, -0.15, -0.02]
    fist[6] = [0.06, -0.10, -0.08]
    fist[7] = [0.04, -0.08, -0.10]
    fist[8] = [0.03, -0.10, -0.08]
    # Middle curled
    fist[9] = [0.0, -0.16, -0.02]
    fist[10] = [0.0, -0.11, -0.08]
    fist[11] = [0.0, -0.09, -0.10]
    fist[12] = [0.0, -0.11, -0.08]
    # Ring curled
    fist[13] = [-0.08, -0.15, -0.02]
    fist[14] = [-0.06, -0.10, -0.08]
    fist[15] = [-0.04, -0.08, -0.10]
    fist[16] = [-0.03, -0.10, -0.08]
    # Pinky curled
    fist[17] = [-0.14, -0.12, -0.02]
    fist[18] = [-0.10, -0.08, -0.08]
    fist[19] = [-0.08, -0.06, -0.10]
    fist[20] = [-0.07, -0.08, -0.08]

    # Straight finger templates
    # Index straight up
    index_up = [
        [0.08, -0.18, -0.02],
        [0.10, -0.32, -0.04],
        [0.11, -0.42, -0.05],
        [0.12, -0.52, -0.06]
    ]
    # Middle straight up
    middle_up = [
        [0.0, -0.20, -0.02],
        [0.0, -0.36, -0.04],
        [0.0, -0.48, -0.05],
        [0.0, -0.58, -0.06]
    ]

    # ------------------ GESTURE 0: THUMBS UP (Volume Up) ------------------
    thumbs_up = np.zeros((21, 3))
    thumbs_up[0] = [0.0, 0.0, 0.0]
    # Thumb pointing up (decreased Y)
    thumbs_up[1] = [0.05, -0.08, -0.02]
    thumbs_up[2] = [0.08, -0.18, -0.04]
    thumbs_up[3] = [0.10, -0.28, -0.05]
    thumbs_up[4] = [0.12, -0.38, -0.06]
    # Rest are curled
    for idx in range(5, 21):
        thumbs_up[idx] = fist[idx]
    gestures["Volume Up"] = thumbs_up

    # ------------------ GESTURE 1: THUMBS DOWN (Volume Down) ------------------
    # A thumbs down is simply a thumbs up rotated 180 degrees (negating X and Y coordinates)
    thumbs_down = np.zeros((21, 3))
    for idx in range(21):
        thumbs_down[idx] = [-thumbs_up[idx][0], -thumbs_up[idx][1], thumbs_up[idx][2]]
    gestures["Volume Down"] = thumbs_down

    # ------------------ GESTURE 2: RAISED HAND (Play/Pause) ------------------
    # All fingers straight up (Open Palm)
    raised_hand = np.zeros((21, 3))
    raised_hand[0] = [0.0, 0.0, 0.0]
    # Thumb pointing up/slanted
    raised_hand[1] = [0.05, -0.08, -0.02]
    raised_hand[2] = [0.10, -0.16, -0.04]
    raised_hand[3] = [0.14, -0.23, -0.05]
    raised_hand[4] = [0.18, -0.30, -0.06]
    # Index straight up
    raised_hand[5:9] = index_up
    # Middle straight up
    raised_hand[9:13] = middle_up
    # Ring straight up
    raised_hand[13] = [-0.08, -0.18, -0.02]
    raised_hand[14] = [-0.10, -0.32, -0.04]
    raised_hand[15] = [-0.11, -0.42, -0.05]
    raised_hand[16] = [-0.12, -0.52, -0.06]
    # Pinky straight up
    raised_hand[17] = [-0.14, -0.15, -0.02]
    raised_hand[18] = [-0.18, -0.26, -0.04]
    raised_hand[19] = [-0.20, -0.35, -0.05]
    raised_hand[20] = [-0.22, -0.44, -0.06]
    gestures["Play/Pause"] = raised_hand

    # ------------------ GESTURE 4: TWO LEFT FINGER (Previous) ------------------
    # Index + Middle pointing left (negative X axis, Y stays flat)
    two_left = np.zeros((21, 3))
    two_left[0] = [0.0, 0.0, 0.0]
    # Thumb curled
    two_left[1] = fist[1]
    two_left[2] = fist[2]
    two_left[3] = fist[3]
    two_left[4] = fist[4]
    # Index pointing left
    two_left[5] = [-0.08, -0.2, -0.02]
    two_left[6] = [-0.20, -0.2, -0.04]
    two_left[7] = [-0.30, -0.2, -0.05]
    two_left[8] = [-0.40, -0.2, -0.06]
    # Middle pointing left
    two_left[9] = [-0.08, -0.26, -0.02]
    two_left[10] = [-0.20, -0.26, -0.04]
    two_left[11] = [-0.30, -0.26, -0.05]
    two_left[12] = [-0.40, -0.26, -0.06]
    # Ring & Pinky curled
    for idx in range(13, 21):
        two_left[idx] = fist[idx]
    gestures["Next"] = two_left

    # ------------------ GESTURE 5: TWO RIGHT FINGER (Previous) ------------------
    # Index + Middle pointing right (positive X axis, Y stays flat)
    two_right = np.zeros((21, 3))
    two_right[0] = [0.0, 0.0, 0.0]
    # Thumb curled
    two_right[1] = fist[1]
    two_right[2] = fist[2]
    two_right[3] = fist[3]
    two_right[4] = fist[4]
    # Index pointing right
    two_right[5] = [0.08, -0.2, -0.02]
    two_right[6] = [0.20, -0.2, -0.04]
    two_right[7] = [0.30, -0.2, -0.05]
    two_right[8] = [0.40, -0.2, -0.06]
    # Middle pointing right
    two_right[9] = [0.08, -0.26, -0.02]
    two_right[10] = [0.20, -0.26, -0.04]
    two_right[11] = [0.30, -0.26, -0.05]
    two_right[12] = [0.40, -0.26, -0.06]
    # Ring & Pinky curled
    for idx in range(13, 21):
        two_right[idx] = fist[idx]
    gestures["Previous"] = two_right

    # ------------------ GESTURE 6: IDLE / REST (Idle) ------------------
    # Relaxed hand, slightly curved
    idle = np.zeros((21, 3))
    idle[0] = [0.0, 0.0, 0.0]
    # Thumb straight
    idle[1] = [0.08, -0.05, -0.02]
    idle[2] = [0.13, -0.10, -0.04]
    idle[3] = [0.16, -0.13, -0.05]
    idle[4] = [0.18, -0.15, -0.06]
    # Rest are semi-curled
    for idx in range(5, 21):
        # average between straight palm and fist
        idle[idx] = 0.5 * fist[idx] + 0.25 * fist[idx] # slightly relaxed fist
    gestures["Idle"] = idle

    return gestures

def generate_csv_dataset():
    print("Generating custom pre-defined gesture dataset...")
    gestures = generate_base_gestures()
    
    # Save mapping file
    mapping = {str(idx): name for idx, name in enumerate(gestures.keys())}
    with open(MAP_PATH, "w") as f:
        json.dump(mapping, f, indent=4)
    print(f"Saved gesture mapping: {mapping}")
    
    num_samples_per_gesture = 250
    
    with open(CSV_DATA_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        
        for class_idx, (name, base_coords) in enumerate(gestures.items()):
            print(f"Creating samples for '{name}' (Class {class_idx})...")
            for _ in range(num_samples_per_gesture):
                noise = np.random.normal(0, 0.025, base_coords.shape)
                noisy_coords = base_coords + noise
                noisy_coords[0] = [0.0, 0.0, 0.0]
                norm_features = normalize_landmarks(noisy_coords.tolist())
                row = [class_idx] + norm_features
                writer.writerow(row)
                
    print(f"Dataset successfully written to {CSV_DATA_PATH}")

def train_default_model():
    print("Starting default training sequence...")
    manager = GestureModelManager()
    result = manager.train_model(epochs=120, batch_size=32, lr=0.002)
    print(f"Training completed: {result}")

if __name__ == "__main__":
    generate_csv_dataset()
    train_default_model()

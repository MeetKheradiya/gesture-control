import os
import csv
import json
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from backend.config import DATA_DIR

# Paths for models and data
CSV_DATA_PATH = DATA_DIR / "gestures.csv"
MODEL_PATH = DATA_DIR / "gesture_model.pth"
MAP_PATH = DATA_DIR / "gesture_map.json"

def normalize_landmarks(landmarks):
    """
    Normalizes a list of 21 landmarks (each having x, y, z).
    1. Translates the wrist (landmark 0) to (0, 0, 0).
    2. Scales the landmarks so the maximum distance from the wrist is 1.0.
    """
    coords = np.array(landmarks, dtype=np.float32).reshape(21, 3)
    
    # 1. Translate wrist to origin
    wrist = coords[0]
    translated = coords - wrist
    
    # 2. Scale to unit sphere
    distances = np.linalg.norm(translated, axis=1)
    max_dist = np.max(distances)
    if max_dist > 0:
        normalized = translated / max_dist
    else:
        normalized = translated
        
    return normalized.flatten().tolist()

class GestureClassifierNet(nn.Module):
    """
    Lightweight MLP for classification of hand landmarks.
    Input size: 63 (21 landmarks * 3 coords)
    """
    def __init__(self, num_classes):
        super(GestureClassifierNet, self).__init__()
        self.network = nn.Sequential(
            nn.Linear(63, 128),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, num_classes)
        )
        
    def forward(self, x):
        return self.network(x)

class GestureDataset(Dataset):
    """
    PyTorch Dataset for landmarks loaded from CSV.
    """
    def __init__(self, csv_file):
        self.inputs = []
        self.labels = []
        
        if os.path.exists(csv_file):
            with open(csv_file, "r") as f:
                reader = csv.reader(f)
                for row in reader:
                    if not row:
                        continue
                    label = int(row[0])
                    landmarks = [float(val) for val in row[1:]]
                    self.inputs.append(landmarks)
                    self.labels.append(label)
                    
        self.inputs = torch.tensor(self.inputs, dtype=torch.float32)
        self.labels = torch.tensor(self.labels, dtype=torch.long)
        
    def __len__(self):
        return len(self.labels)
        
    def __getitem__(self, idx):
        return self.inputs[idx], self.labels[idx]

class GestureModelManager:
    """
    Manages training, inference, and persistence of the gesture classifier.
    """
    def __init__(self):
        self.model = None
        self.gesture_map = {}  # Index (str) -> Gesture Name (str)
        self.load_model()

    def load_model(self):
        """Loads model weights and gesture mapping from disk."""
        if MAP_PATH.exists():
            with open(MAP_PATH, "r") as f:
                self.gesture_map = json.load(f)
                
        num_classes = len(self.gesture_map)
        if num_classes > 0 and MODEL_PATH.exists():
            try:
                self.model = GestureClassifierNet(num_classes)
                # Map to CPU by default (suitable for Pi & PC without GPU overhead)
                self.model.load_state_dict(torch.load(MODEL_PATH, map_location=torch.device('cpu')))
                self.model.eval()
                print(f"Loaded gesture model with {num_classes} classes.")
            except Exception as e:
                print(f"Failed to load model: {e}")
                self.model = None
        else:
            print("No model or gesture mapping found on disk. Dynamic training needed.")
            self.model = None

    def predict(self, landmarks):
        """
        Takes raw landmarks, normalizes them, and runs inference.
        Returns: (gesture_name, confidence)
        """
        if self.model is None or not self.gesture_map:
            return "Unknown", 0.0
            
        try:
            norm_features = normalize_landmarks(landmarks)
            inp_tensor = torch.tensor([norm_features], dtype=torch.float32)
            
            with torch.no_grad():
                outputs = self.model(inp_tensor)
                probabilities = torch.softmax(outputs, dim=1)[0]
                max_prob, max_idx = torch.max(probabilities, dim=0)
                
                class_idx = str(max_idx.item())
                confidence = max_prob.item()
                
                gesture_name = self.gesture_map.get(class_idx, "Unknown")
                return gesture_name, confidence
        except Exception as e:
            print(f"Prediction error: {e}")
            return "Error", 0.0

    def record_sample(self, gesture_name, landmarks):
        """
        Saves a normalized training sample to the CSV file.
        Updates the local gesture map if new.
        """
        # Read or create gesture map
        if MAP_PATH.exists():
            with open(MAP_PATH, "r") as f:
                self.gesture_map = json.load(f)
                
        # Find index for gesture name
        name_to_idx = {v: k for k, v in self.gesture_map.items()}
        if gesture_name in name_to_idx:
            label_idx = int(name_to_idx[gesture_name])
        else:
            # Create a new index
            label_idx = len(self.gesture_map)
            self.gesture_map[str(label_idx)] = gesture_name
            with open(MAP_PATH, "w") as f:
                json.dump(self.gesture_map, f, indent=4)
                
        # Normalize and append to CSV
        norm_features = normalize_landmarks(landmarks)
        row = [label_idx] + norm_features
        
        with open(CSV_DATA_PATH, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(row)
            
        return len(norm_features)

    def train_model(self, epochs=100, batch_size=32, lr=0.001):
        """
        Trains the PyTorch model on the collected CSV dataset.
        Returns: dict with training status, accuracy, and loss history.
        """
        if not CSV_DATA_PATH.exists():
            return {"success": False, "error": "No training dataset found (CSV does not exist)."}
            
        dataset = GestureDataset(CSV_DATA_PATH)
        if len(dataset) < 10:
            return {"success": False, "error": f"Insufficient training data. Only {len(dataset)} samples. Record more!"}
            
        # Determine number of classes from current mapping file
        if not MAP_PATH.exists():
            return {"success": False, "error": "No gesture mapping found. Record some gestures first."}
            
        with open(MAP_PATH, "r") as f:
            self.gesture_map = json.load(f)
            
        num_classes = len(self.gesture_map)
        if num_classes < 2:
            return {"success": False, "error": "Need at least 2 distinct gestures to train the classifier."}
            
        # Split train/val (80/20)
        train_size = int(0.8 * len(dataset))
        val_size = len(dataset) - train_size
        train_dataset, val_dataset = torch.utils.data.random_split(dataset, [train_size, val_size])
        
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
        
        # Instantiate model
        model = GestureClassifierNet(num_classes)
        criterion = nn.CrossEntropyLoss()
        optimizer = optim.Adam(model.parameters(), lr=lr)
        
        loss_history = []
        val_acc = 0.0
        
        for epoch in range(epochs):
            model.train()
            epoch_loss = 0.0
            for inputs, labels in train_loader:
                optimizer.zero_grad()
                outputs = model(inputs)
                loss = criterion(outputs, labels)
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item() * inputs.size(0)
            
            epoch_loss /= len(train_loader.dataset)
            loss_history.append(epoch_loss)
            
            # Validation
            model.eval()
            correct = 0
            total = 0
            with torch.no_grad():
                for inputs, labels in val_loader:
                    outputs = model(inputs)
                    _, predicted = torch.max(outputs, 1)
                    total += labels.size(0)
                    correct += (predicted == labels).sum().item()
            
            val_acc = correct / total if total > 0 else 0.0
            
        # Save model
        torch.save(model.state_dict(), MODEL_PATH)
        
        # Re-initialize current model
        self.model = model
        self.model.eval()
        
        return {
            "success": True,
            "samples": len(dataset),
            "classes": num_classes,
            "val_accuracy": val_acc,
            "final_loss": loss_history[-1],
            "loss_history": loss_history
        }

    def clear_dataset(self):
        """Resets training data and model mappings."""
        if CSV_DATA_PATH.exists():
            CSV_DATA_PATH.unlink()
        if MODEL_PATH.exists():
            MODEL_PATH.unlink()
        if MAP_PATH.exists():
            MAP_PATH.unlink()
        self.model = None
        self.gesture_map = {}
        return {"success": True, "message": "Dataset cleared."}

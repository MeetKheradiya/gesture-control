import sys
import os

# Add workspace directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.model import GestureModelManager

def main():
    print("AuraCast Gesture Model Offline Training Utility")
    print("-----------------------------------------------")
    
    manager = GestureModelManager()
    
    # Check if dataset exists
    from backend.model import CSV_DATA_PATH
    if not CSV_DATA_PATH.exists():
        print(f"Error: Dataset file not found at {CSV_DATA_PATH}.")
        print("Please run backend/generate_default_dataset.py to create a default dataset,")
        print("or collect samples using the Web UI first.")
        return
        
    print(f"Dataset found. Starting training workflow on {CSV_DATA_PATH}...")
    
    # Prompt training params
    epochs = 100
    batch_size = 32
    lr = 0.001
    
    result = manager.train_model(epochs=epochs, batch_size=batch_size, lr=lr)
    
    if result["success"]:
        print("\nTraining Success!")
        print(f"- Total Samples Processed: {result['samples']}")
        print(f"- Unique Gesture Classes: {result['classes']}")
        print(f"- Validation Accuracy: {result['val_accuracy'] * 100:.2f}%")
        print(f"- Final Model Loss: {result['final_loss']:.6f}")
        print("\nModel saved to backend data directory successfully.")
    else:
        print(f"\nTraining Failed: {result.get('error')}")

if __name__ == "__main__":
    main()

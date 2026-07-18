import os
import sys
import subprocess
import shutil
from pathlib import Path

def package_app():
    print("AuraCast Desktop Application Packaging Utility")
    print("---------------------------------------------")
    
    # Paths setup
    workspace_dir = Path(__file__).resolve().parent
    entry_point = workspace_dir / "app_gui.py"
    dist_dir = workspace_dir / "dist"
    build_dir = workspace_dir / "build"
    spec_file = workspace_dir / "AuraCast.spec"
    
    # Check entry point
    if not entry_point.exists():
        print(f"Error: Entry point '{entry_point}' not found.")
        return False
        
    print(f"Found entry point at {entry_point}")
    print("Resolving PyInstaller command...")
    
    # Under Windows/Linux/Pi, we run PyInstaller
    # Find PyInstaller executable in current python scripts directory
    pyinstaller_cmd = "pyinstaller"
    
    # We will build with --onedir (folder mode) for faster launches and better debugging.
    # Add data files (MediaPipe .task and pre-trained weights)
    # Target format for --add-data: "src;dest" on Windows, "src:dest" on Unix
    sep = ";" if sys.platform.startswith("win") else ":"
    
    # Ensure default dataset and mappings exist
    data_dir = workspace_dir / "data"
    default_dataset_script = workspace_dir / "backend" / "generate_default_dataset.py"
    if not (data_dir / "gesture_model.pth").exists():
        print("Pre-trained model weights missing. Running default trainer first...")
        try:
            subprocess.run([sys.executable, str(default_dataset_script)], check=True)
        except Exception as e:
            print(f"Failed to run default dataset generator: {e}")
            return False

    # Collect model assets to bundle
    add_data_args = []
    
    # 1. Bundle hand_landmarker.task
    task_model = data_dir / "hand_landmarker.task"
    if task_model.exists():
        add_data_args.append(f"--add-data={str(task_model)}{sep}data")
        
    # 2. Bundle trained weights & mappings
    model_weights = data_dir / "gesture_model.pth"
    if model_weights.exists():
        add_data_args.append(f"--add-data={str(model_weights)}{sep}data")
        
    model_map = data_dir / "gesture_map.json"
    if model_map.exists():
        add_data_args.append(f"--add-data={str(model_map)}{sep}data")
        
    # 3. Bundle Face Authentication cascades
    import cv2
    cascade_dir = Path(cv2.__file__).resolve().parent / "data"
    if cascade_dir.exists():
        add_data_args.append(f"--add-data={str(cascade_dir)}{sep}cv2/data")

    # Command argument assembly
    cmd = [
        pyinstaller_cmd,
        "--name=AuraCast",
        "--noconfirm",
        "--windowed", # Hide console on windows
        "--clean",
        f"--workpath={str(build_dir)}",
        f"--distpath={str(dist_dir)}",
    ] + add_data_args + [
        # Hidden imports for critical dynamic loaders
        "--hidden-import=PySide6.QtCore",
        "--hidden-import=PySide6.QtWidgets",
        "--hidden-import=PySide6.QtGui",
        "--hidden-import=qasync",
        "--hidden-import=torch",
        "--hidden-import=numpy",
        "--hidden-import=cv2",
        "--hidden-import=mediapipe",
        str(entry_point)
    ]
    
    print(f"\nExecuting PyInstaller command:\n{' '.join(cmd)}\n")
    
    try:
        # Run PyInstaller
        result = subprocess.run(cmd, check=True)
        if result.returncode == 0:
            print("\nPackaging completed successfully!")
            print(f"Standalone application available at: {dist_dir / 'AuraCast'}")
            return True
    except subprocess.CalledProcessError as e:
        print(f"\nPyInstaller compilation failed: {e}")
        return False
    except FileNotFoundError:
        print("\nError: PyInstaller not found. Install it using 'pip install pyinstaller'.")
        return False

if __name__ == "__main__":
    package_app()

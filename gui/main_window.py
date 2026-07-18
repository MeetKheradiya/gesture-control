import asyncio
import time
from PySide6.QtCore import Slot, Qt, QSize
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout, 
    QGridLayout, QGroupBox, QPushButton, QLabel, QListWidget, 
    QLineEdit, QComboBox, QSpinBox, QSlider, QCheckBox, QTextEdit, QMessageBox
)
from PySide6.QtGui import QIcon, QFont

from backend.config import config
from backend.tv_drivers import scan_network_devices, execute_tv_command
from gui.camera_widget import CameraThread, CameraWidget
from gui.style import DARK_THEME, LIGHT_THEME

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AuraCast AI Smart TV Controller")
        self.resize(1024, 768)
        
        # Initialize background processing thread
        self.camera_thread = CameraThread()
        self.camera_thread.log_emitted.connect(self.log_message)
        
        self.init_ui()
        self.set_theme(dark=True)
        
        # Start camera capture
        self.camera_thread.start()

    def init_ui(self):
        # Central widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Layout structure
        main_layout = QVBoxLayout(self.central_widget)
        
        # Application Header
        header_layout = QHBoxLayout()
        logo_label = QLabel(" AuraCast Dashboard")
        logo_font = QFont("Outfit", 18, QFont.Bold)
        logo_label.setFont(logo_font)
        logo_label.setStyleSheet("color: #00f2fe;")
        
        self.theme_btn = QPushButton("Light Mode")
        self.theme_btn.setFixedWidth(100)
        self.theme_btn.clicked.connect(self.toggle_theme)
        
        header_layout.addWidget(logo_label)
        header_layout.addStretch()
        header_layout.addWidget(self.theme_btn)
        main_layout.addLayout(header_layout)
        
        # Camera preview widget added directly (no tabs!)
        self.camera_widget = CameraWidget(self.camera_thread)
        main_layout.addWidget(self.camera_widget)

    def log_message(self, msg, level="info"):
        print(f"[{level.upper()}] {msg}")

    def trigger_manual_cmd(self, cmd_name):
        self.log_message(f"Triggering manual key command: '{cmd_name}'", "info")
        success = execute_tv_command(cmd_name)
        if success:
            self.log_message(f"Manual command '{cmd_name}' executed SUCCESS.", "success")
        else:
            self.log_message(f"Manual command '{cmd_name}' failed to execute.", "danger")

    def toggle_theme(self):
        if self.theme_btn.text() == "Light Mode":
            self.set_theme(dark=False)
            self.theme_btn.setText("Dark Mode")
        else:
            self.set_theme(dark=True)
            self.theme_btn.setText("Light Mode")

    def set_theme(self, dark=True):
        if dark:
            self.setStyleSheet(DARK_THEME)
        else:
            self.setStyleSheet(LIGHT_THEME)

    # Trainer methods
    def add_custom_pose_label(self):
        label = self.new_pose_input.text().strip()
        if not label: return
        self.pose_list.addItem(label)
        self.new_pose_input.clear()
        self.log_message(f"Registered custom pose command target: '{label}'")

    def record_pose(self):
        selected_item = self.pose_list.currentItem()
        if not selected_item:
            QMessageBox.warning(self, "Warning", "Please select a pose command from the list first!")
            return
            
        pose_name = selected_item.text()
        self.log_message(f"Dataset recording for '{pose_name}' will begin in 2 seconds. Hold position...")
        
        # Delay recording slightly so user can position hand
        self.btn_record.setEnabled(False)
        def start_rec():
            self.camera_thread.start_recording(pose_name, 100)
            self.btn_record.setEnabled(True)
            
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2000, start_rec)

    def train_model(self):
        self.btn_train.setEnabled(False)
        self.log_message("Starting PyTorch classifier network training workflow...", "info")
        
        # Local runner inside a thread to prevent freezing
        class TrainThread(QThread):
            finished_signal = Signal(dict)
            def run(self):
                from backend.model import GestureModelManager
                manager = GestureModelManager()
                result = manager.train_model()
                self.finished_signal.emit(result)
                
        self.train_worker = TrainThread(self)
        self.train_worker.finished_signal.connect(self.model_training_completed)
        self.train_worker.start()

    def model_training_completed(self, result):
        self.btn_train.setEnabled(True)
        if result["success"]:
            self.log_message("Neural network training COMPLETED!", "success")
            self.log_message(f"- Samples Processed: {result['samples']}", "success")
            self.log_message(f"- Unique Poses: {result['classes']}", "success")
            self.log_message(f"- Model Accuracy: {result['val_accuracy']*100:.2f}%", "success")
            # Reload weights
            self.camera_thread.model_manager.load_model()
        else:
            self.log_message(f"Training FAILED: {result.get('error')}", "danger")

    def clear_dataset(self):
        reply = QMessageBox.question(self, "Clear Dataset", 
                                     "Delete all saved coordinates and model weights? This cannot be undone!",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.camera_thread.model_manager.clear_dataset()
            self.log_message("Workspace training datasets completely cleared.", "warning")

    # Face Registration
    def register_face(self):
        self.log_message("Position your face in front of the camera. Face registration starts in 2 seconds...")
        
        def start_reg():
            self.camera_thread.start_face_profiling(30)
            
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2000, start_reg)

    def clear_face_profile(self):
        self.camera_thread.face_auth.clear_profile()
        self.log_message("Facial lockout profile deleted.", "warning")

    # Save & Apply Settings
    def apply_settings(self):
        driver = self.driver_select.currentText()
        tv_protocol = self.tv_type.currentText()
        tv_ip_address = self.tv_ip.text().strip()
        serial_com_port = self.serial_port.text().strip()
        cam_index = self.cam_spin.value()
        confidence = self.conf_slider.value() / 100.0
        face_lockout = self.face_auth_chk.isChecked()
        
        # Check if camera index changed (requires thread restart)
        restart_camera = cam_index != config.get("camera_index")
        
        config.set("active_driver", driver)
        config.set("wifi_tv_type", tv_protocol)
        config.set("wifi_tv_ip", tv_ip_address)
        config.set("serial_port", serial_com_port)
        config.set("camera_index", cam_index)
        config.set("confidence_threshold", confidence)
        config.set("face_lockout_enabled", face_lockout)
        
        self.log_message("System configurations saved successfully.", "success")
        
        if restart_camera:
            self.log_message("Webcam source index changed. Restarting capture engine...", "warning")
            self.camera_thread.stop()
            self.camera_thread.start()

    # Async scanning helper using qasync
    def scan_subnet(self):
        self.log_message("Scanning local network subnet for active Smart TVs...", "info")
        
        # Define async helper using qasync
        async def run_scan():
            loop = asyncio.get_event_loop()
            # Run scan in threadpool to prevent UI lockup since socket timeouts can block
            devices = await loop.run_in_executor(None, scan_network_devices)
            
            if devices:
                self.log_message(f"Detected {len(devices)} active network devices:", "success")
                for dev in devices:
                    self.log_message(f"- {dev['type']} found at IP: {dev['ip']}", "success")
                # Auto fill first device found
                self.tv_ip.setText(devices[0]["ip"])
                # Match type combobox
                for idx in range(self.tv_type.count()):
                    if self.tv_type.itemText(idx).lower() in devices[0]["type"].lower():
                        self.tv_type.setCurrentIndex(idx)
                        break
            else:
                self.log_message("No active Smart TVs detected on local subnet. Verify network credentials.", "warning")
                
        asyncio.create_task(run_scan())

    def closeEvent(self, event):
        # Shut down camera threads safely
        self.camera_thread.stop()
        event.accept()

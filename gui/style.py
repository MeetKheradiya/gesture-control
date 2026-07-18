# Modern stylesheet definitions for AuraCast PySide6 Desktop GUI

DARK_THEME = """
QMainWindow {
    background-color: #0b0c10;
}

QWidget {
    color: #c5c6c7;
    font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}

/* Tab Widget styling */
QTabWidget::pane {
    border: 1px solid #1f2833;
    background-color: #12131c;
    border-radius: 8px;
}

QTabBar::tab {
    background: #1f2833;
    border: 1px solid #1f2833;
    border-bottom-color: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 16px;
    margin-right: 2px;
    font-weight: 500;
}

QTabBar::tab:selected {
    background: #12131c;
    border-color: #1f2833;
    border-bottom: 2px solid #00f2fe;
    color: #00f2fe;
}

QTabBar::tab:hover {
    background: #2b3a4a;
}

/* GroupBox Card Panel */
QGroupBox {
    border: 1px solid #1f2833;
    border-radius: 8px;
    margin-top: 1.5em;
    background-color: rgba(22, 24, 38, 0.6);
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px 0 5px;
    color: #00f2fe;
}

/* Buttons styling */
QPushButton {
    background-color: #1f2833;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 8px 14px;
    color: #f3f4f6;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #2e3d52;
    border-color: #00f2fe;
}

QPushButton:pressed {
    background-color: #131b26;
}

QPushButton#btn_primary {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00f2fe, stop:1 #9b51e0);
    border: none;
    color: #ffffff;
}

QPushButton#btn_primary:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2bf6ff, stop:1 #ae6bf2);
}

QPushButton#btn_danger {
    background-color: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.3);
    color: #f43f5e;
}

QPushButton#btn_danger:hover {
    background-color: #ef4444;
    color: #ffffff;
}

/* Remote Control Buttons */
QPushButton.remote-btn {
    background-color: #1a1c2e;
    border: 1px solid #2d304f;
    border-radius: 8px;
    padding: 14px 10px;
    font-size: 11px;
}

QPushButton.remote-btn:hover {
    background-color: #242742;
    border-color: #00f2fe;
}

QPushButton.remote-btn:pressed {
    background-color: #0e101b;
}

QPushButton.remote-power {
    border-color: rgba(244, 63, 94, 0.4);
    color: #f43f5e;
}

QPushButton.remote-power:hover {
    background-color: rgba(244, 63, 94, 0.15);
    border-color: #f43f5e;
}

/* Inputs, Spinboxes and Comboboxes */
QLineEdit, QComboBox, QSpinBox {
    background-color: #0b0c10;
    border: 1px solid #1f2833;
    border-radius: 6px;
    padding: 6px 12px;
    color: #f3f4f6;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border-color: #00f2fe;
}

QComboBox::drop-down {
    border: none;
}

/* Progress bar styling */
QProgressBar {
    border: 1px solid #1f2833;
    border-radius: 4px;
    text-align: center;
    background-color: #0b0c10;
}

QProgressBar::chunk {
    background-color: #00f2fe;
    width: 10px;
}

/* Logger Terminal */
QTextEdit#console_log {
    background-color: #050508;
    border: 1px solid #1f2833;
    border-radius: 6px;
    font-family: 'JetBrains Mono', 'Consolas', monospace;
    font-size: 11px;
    color: #00f2fe;
    padding: 8px;
}

/* List Widget */
QListWidget {
    background-color: rgba(0, 0, 0, 0.2);
    border: 1px solid #1f2833;
    border-radius: 6px;
    padding: 4px;
}

QListWidget::item {
    background-color: rgba(255, 255, 255, 0.02);
    border-bottom: 1px solid #1f2833;
    padding: 8px;
    border-radius: 4px;
    margin-bottom: 4px;
}

QListWidget::item:hover {
    background-color: rgba(255, 255, 255, 0.06);
}

/* Slider */
QSlider::groove:horizontal {
    border: 1px solid #1f2833;
    height: 6px;
    background: #1f2833;
    margin: 2px 0;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #00f2fe;
    border: 1px solid #00f2fe;
    width: 14px;
    height: 14px;
    margin: -4px 0;
    border-radius: 7px;
}

QSlider::handle:horizontal:hover {
    background: #2bf6ff;
    transform: scale(1.2);
}
"""

LIGHT_THEME = """
QMainWindow {
    background-color: #f8fafc;
}

QWidget {
    color: #334155;
    font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}

QTabWidget::pane {
    border: 1px solid #cbd5e1;
    background-color: #ffffff;
    border-radius: 8px;
}

QTabBar::tab {
    background: #e2e8f0;
    border: 1px solid #cbd5e1;
    border-bottom-color: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 16px;
    margin-right: 2px;
    font-weight: 500;
}

QTabBar::tab:selected {
    background: #ffffff;
    border-color: #cbd5e1;
    border-bottom: 2px solid #9b51e0;
    color: #9b51e0;
}

QTabBar::tab:hover {
    background: #f1f5f9;
}

QGroupBox {
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    margin-top: 1.5em;
    background-color: #ffffff;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px 0 5px;
    color: #9b51e0;
}

QPushButton {
    background-color: #f1f5f9;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 8px 14px;
    color: #334155;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #e2e8f0;
    border-color: #9b51e0;
}

QPushButton:pressed {
    background-color: #cbd5e1;
}

QPushButton#btn_primary {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00f2fe, stop:1 #9b51e0);
    border: none;
    color: #ffffff;
}

QPushButton#btn_primary:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2bf6ff, stop:1 #ae6bf2);
}

QPushButton#btn_danger {
    background-color: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.2);
    color: #ef4444;
}

QPushButton#btn_danger:hover {
    background-color: #ef4444;
    color: #ffffff;
}

QPushButton.remote-btn {
    background-color: #f8fafc;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 14px 10px;
    font-size: 11px;
}

QPushButton.remote-btn:hover {
    background-color: #e2e8f0;
    border-color: #9b51e0;
}

QPushButton.remote-power {
    border-color: rgba(239, 68, 68, 0.4);
    color: #ef4444;
}

QPushButton.remote-power:hover {
    background-color: rgba(239, 68, 68, 0.1);
    border-color: #ef4444;
}

QLineEdit, QComboBox, QSpinBox {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 12px;
    color: #334155;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border-color: #9b51e0;
}

QProgressBar {
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    text-align: center;
    background-color: #e2e8f0;
}

QProgressBar::chunk {
    background-color: #9b51e0;
    width: 10px;
}

QTextEdit#console_log {
    background-color: #f8fafc;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    font-family: 'JetBrains Mono', 'Consolas', monospace;
    font-size: 11px;
    color: #334155;
    padding: 8px;
}

QListWidget {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 4px;
}

QListWidget::item {
    background-color: #f1f5f9;
    border-bottom: 1px solid #cbd5e1;
    padding: 8px;
    border-radius: 4px;
    margin-bottom: 4px;
}

QListWidget::item:hover {
    background-color: #e2e8f0;
}

QSlider::groove:horizontal {
    border: 1px solid #cbd5e1;
    height: 6px;
    background: #e2e8f0;
    margin: 2px 0;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #9b51e0;
    border: 1px solid #9b51e0;
    width: 14px;
    height: 14px;
    margin: -4px 0;
    border-radius: 7px;
}
"""

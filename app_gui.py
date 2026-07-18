import sys
import os
import asyncio
from PySide6.QtWidgets import QApplication
from qasync import QEventLoop

# Add workspace directory to python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from gui.main_window import MainWindow

def main():
    # Setup PySide6 Application
    app = QApplication(sys.argv)
    
    # Enable QAsync event loop wrapper
    # This allows asyncio tasks (LG WebSocket channels, network scanners) to run
    # concurrently on the same main GUI thread.
    event_loop = QEventLoop(app)
    asyncio.set_event_loop(event_loop)
    
    # Initialize Main Interface Window
    main_win = MainWindow()
    main_win.show()
    
    # Execute loop
    with event_loop:
        event_loop.run_forever()

if __name__ == "__main__":
    main()

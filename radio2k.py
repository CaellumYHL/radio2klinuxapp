#!/usr/bin/env python3
"""Radio2k"""

import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt
from ui import TokyoPlayerWindow

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Radio2k")
    
    # Load stylesheet
    qss_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "styles.qss")
    if os.path.exists(qss_path):
        with open(qss_path, "r") as f:
            app.setStyleSheet(f.read())
    
    window = TokyoPlayerWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

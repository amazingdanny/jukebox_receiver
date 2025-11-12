import os
import sys
import threading
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
import signal
signal.signal(signal.SIGINT, signal.SIG_DFL)

os.environ.setdefault("QT_QPA_PLATFORM", os.environ.get("QT_QPA_PLATFORM", "linuxfb"))

from uicontroller import MusicPlayerUI
from audiocontroller import AudioController
from receiver import RaspberryReceiver

LISTEN_IP = "0.0.0.0"
LISTEN_PORT = 5000
MUSIC_FOLDER = "/mnt/usb"

def main():
    app = QApplication(sys.argv)

    # 1) Create UI
    ui = MusicPlayerUI()

    # 2) Create AudioController with UI reference
    audio = AudioController(ui)

    # 3) Attach controller reference to UI so keyboard quit works

    # 4) Show UI, focus keyboard
    ui.showFullScreen()
    ui.setFocusPolicy(Qt.StrongFocus)
    ui.setFocus()
    ui.grabKeyboard()

    # 5) Start receiver in background
    receiver = RaspberryReceiver(LISTEN_IP, LISTEN_PORT, MUSIC_FOLDER, audio, ui)
    if receiver and ui and audio:
        print("All components initialized successfully.")
    t = threading.Thread(target=receiver.receive, daemon=True)
    t.start()

    # 6) Run Qt event loop
    exit_code = app.exec_()

    # stop audio cleanly
    try:
        audio.stop()
    except Exception:
        pass

    sys.exit(exit_code)

if __name__ == "__main__":
    main()

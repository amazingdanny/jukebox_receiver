# pyqt_ui_fixed.py
import sys
import logging
from typing import List, Optional
import os

# keep linuxfb env if you use linux framebuffer
os.environ.setdefault("QT_QPA_FB", "/dev/fb0")

from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QListWidget
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont

log = logging.getLogger("pyqt_ui")
logging.basicConfig(level=logging.INFO)


class MusicPlayerUI(QWidget):
    _sig_update_song = pyqtSignal(str)
    _sig_update_queue = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        #self.controller = None
        self.current_song = "No song playing"

        # connect signals -> slots
        self._sig_update_song.connect(self._on_update_song)
        self._sig_update_queue.connect(self._on_update_queue)

        # window
        self.setWindowTitle("Music Player")
        self.setStyleSheet("background-color: #121212; color: white;")
        self.setGeometry(0, 0, 800, 480)

        # make sure widget can receive key events
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFocus()

        self._build_ui()

        # show initial text and force a paint so you can verify immediately
        self.update_song(self.current_song)

    def _build_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        title = QLabel("🎵 Raspberry Pi Music Player")
        title.setFont(QFont("Sans", 18))
        title.setStyleSheet("color: #E0F7FA;")
        layout.addWidget(title, alignment=Qt.AlignCenter)

        # current song label (smaller than before so it fits)
        self.song_label = QLabel(self.current_song)
        self.song_label.setFont(QFont("Sans", 20, QFont.Bold))
        self.song_label.setStyleSheet("color: #B2FF59; padding: 4px;")
        self.song_label.setWordWrap(True)
        self.song_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.song_label, alignment=Qt.AlignCenter)

        qlabel = QLabel("Up Next:")
        qlabel.setFont(QFont("Sans", 14))
        qlabel.setStyleSheet("color: #FFD54F; margin-top: 6px;")
        layout.addWidget(qlabel, alignment=Qt.AlignLeft)

        self.queue_list = QListWidget()
        self.queue_list.setStyleSheet("""
            QListWidget {
                background-color: #1E1E1E;
                border: 1px solid #333;
                color: white;
                font-size: 20px;
            }
        """)
        # give the queue a bit more space but keep it contained
        self.queue_list.setMinimumHeight(180)
        self.queue_list.setMaximumHeight(220)
        layout.addWidget(self.queue_list)

        self.setLayout(layout)

    # -------------------------
    # Thread-safe public API
    # -------------------------
    def update_song(self, song_name: Optional[str]):
        """
        Public method called by controller. It will ensure the UI update
        happens on the GUI thread, even if this method is called from another thread.
        """
        if not song_name:
            # Use explicit testing text to help you debug null inputs if you like:
            song_name = "<<< NO SONG PROVIDED >>>"
        self.current_song = song_name
        print("Called update_song")

        # Emit signal which is connected to _on_update_song (executes on GUI thread).
        # Using signal guards against non-GUI-thread calls.
        try:
            self._sig_update_song.emit(self.current_song)
        except Exception:
            # fallback: in case signals are broken, schedule direct call on GUI thread
            QTimer.singleShot(0, lambda: self._on_update_song(self.current_song))

    def update_queue(self, songs: List[str]):
        # safe emit to update queue on GUI thread
        try:
            self._sig_update_queue.emit(list(songs or []))
        except Exception:
            QTimer.singleShot(0, lambda: self._on_update_queue(list(songs or [])))

    # -------------------------
    # Slots that run on GUI thread
    # -------------------------
    def _on_update_song(self, song_name: str):
        print("Called _on_update_song")
        log.info(f"_on_update_song called with: {song_name!r}")
        # set label text and immediately process events/paint to ensure visible
        self.song_label.setText(f"Now Playing: {song_name}")
        # Ensure immediate repaint so you can visually confirm change
        QApplication.processEvents()
        self.song_label.repaint()

    def _on_update_queue(self, songs: List[str]):
        log.info("_on_update_queue called, count=%d", len(songs))
        self.queue_list.clear()
        for i, s in enumerate(songs[:10], 1):
            self.queue_list.addItem(f"{i}. {s}")
        QApplication.processEvents()

    # -------------------------
    # Input: keyboard quit
    # -------------------------
    def keyPressEvent(self, event):
        # Only quit via keyboard (Q/Escape)
        if event.key() in (Qt.Key_Q, Qt.Key_Escape):
            QApplication.quit()
        else:
            super().keyPressEvent(event)


# -------------------------
# Quick test runner
# -------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)

    class DummyController:
        def __init__(self):
            self.queue = ["Track 1 - Artist", "Track 2 - Artist", "Track 3 - Artist"]

        def stop(self):
            print("DummyController.stop() called")

    ctrl = DummyController()
    ui = MusicPlayerUI(ctrl)
    ui.showFullScreen()

    # Tests to confirm behavior:
    # 1) initial visible update
    ui.update_song("Test Song — Artist")
    ui.update_queue(ctrl.queue)

    # 2) test delayed update (simulating controller thread)
    def delayed():
        ui.update_song("Delayed Song — after 2s")
    QTimer.singleShot(2000, delayed)

    sys.exit(app.exec_())

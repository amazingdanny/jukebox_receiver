from kivy.config import Config


Config.set('graphics', 'fullscreen', '1')
Config.set('graphics', 'borderless', '1')
Config.set('graphics', 'resizable', '0')

import os
import sys
import threading
import signal
import subprocess

from kivy.app import App
from kivy.core.window import Window
from kivy.config import Config

# Configure Kivy for Raspberry Pi
Config.set('graphics', 'fullscreen', '1')  # True fullscreen
Config.set('graphics', 'width', '800')
Config.set('graphics', 'height', '480')

signal.signal(signal.SIGINT, signal.SIG_DFL)

from uicontroller import MusicPlayerUI
from audiocontroller import AudioController
from receiver import RaspberryReceiver

def find_jukebox():
    result = subprocess.run(
        ["findmnt", "-rn", "-S", "LABEL=JUKEBOX", "-o", "TARGET"],
        capture_output=True,
        text=True
    )
    mount_point = result.stdout.strip()
    if mount_point:
        print(f"mount point: {mount_point}")
        return mount_point
    return "No Path"

LISTEN_IP = "0.0.0.0"
LISTEN_PORT = 5000
MUSIC_FOLDER = find_jukebox()


class MusicPlayerApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ui = None
        self.audio = None
        self.receiver = None

    def build(self):
        # Create UI
        self.ui = MusicPlayerUI()
        
        # Create AudioController with UI reference
        self.audio = AudioController(self.ui)
        
        # Give UI reference to audio controller so buttons work
        self.ui.ui_controller = self.audio
        
        # Bind keyboard events
        Window.bind(on_keyboard=self.ui.on_keyboard)
        
        # Start receiver in background
        self.receiver = RaspberryReceiver(LISTEN_IP, LISTEN_PORT, MUSIC_FOLDER, self.audio, self.ui)
        if self.receiver and self.ui and self.audio:
            print("All components initialized successfully.")
        
        t = threading.Thread(target=self.receiver.receive, daemon=True)
        t.start()
        
        return self.ui

    def on_stop(self):
        """Called when the app is closing."""
        try:
            if self.audio:
                self.audio.stop()
        except Exception as e:
            print(f"Error stopping audio: {e}")
        return True


def main():
    app = MusicPlayerApp()
    app.run()


if __name__ == "__main__":
    main()

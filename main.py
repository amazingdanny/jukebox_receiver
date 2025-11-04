#!/usr/bin/env python3
from audiocontroller import AudioController
from receiver import RaspberryReceiver
from uicontroller import UIController
import threading
import time


class MusicApp:
    def __init__(self):
        self.ui_controller = UIController()
        self.audio_controller = AudioController(self.ui_controller)

        # Pass UI controller to receiver so it can update logs
        self.receiver = RaspberryReceiver("0.0.0.0", 5000, '/mnt/usb', self.audio_controller, self.ui_controller)
        self.current_queue = []

    def start(self):
        print("Starting Raspberry Music Player...")

        # Start UI
        self.ui_controller.start()

        # Update UI with initial state
        self.ui_controller.update_song("No song playing")
        self.ui_controller.update_queue([])
        self.ui_controller.update_volume(50)

        # Start network receiver in separate thread
        receiver_thread = threading.Thread(target=self.receiver.receive)
        receiver_thread.daemon = True
        receiver_thread.start()

        print("Music Player started successfully!")
        print("UI is running, receiver is listening on port 5000")

        # Keep main thread alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Shutting down...")
            self.ui_controller.stop()


def main():
    app = MusicApp()
    app.start()


if __name__ == "__main__":
    main()
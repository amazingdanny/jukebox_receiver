import vlc
import threading
import time
from queue import Queue

class AudioController:
    def __init__(self):
        self.queue = Queue()
        self.player = vlc.MediaPlayer()
        self.player.audio_output_set("alsa")
        self.player.audio_output_device_set(None, "alsa://hw:1,0")
        self.lock = threading.Lock()
        self.skip_flag = threading.Event()
        self.thread = threading.Thread(target=self._playback_loop, daemon=True)
        self.thread.start()

    def _playback_loop(self):
        """Continuously check for new tracks and play them in order."""
        while True:
            filepath = self.queue.get()  # Wait for next track
            self._play(filepath)
            self._wait_until_finished()
            self.queue.task_done()

    def _play(self, filepath):
        with self.lock:
            if self.player and self.player.is_playing():
                self.player.stop()
            media = vlc.Media(filepath)
            self.player.set_media(media)
            self.player.audio_output_set("alsa")
            self.player.audio_output_device_set(None, "hw:1,0")
            self.player.play() 

    def _wait_until_finished(self):
        """Block until the current track finishes playing or skip is requested."""
        self.skip_flag.clear()
        while self.is_playing() and not self.skip_flag.is_set():
            time.sleep(0.1)
        if self.skip_flag.is_set():
            self.stop()

    def play(self, filepath):
        """Add a file to the queue."""
        self.queue.put(filepath)

    def stop(self):
        """Stop playback and clear queue."""
        with self.lock:
            if self.player and self.player.is_playing():
                self.player.stop()
            # Clear queue
            with self.queue.mutex:
                self.queue.queue.clear()

    def skip(self):
        """Skip the current song and move to the next one in the queue."""
        self.skip_flag.set()

    def is_playing(self):
        with self.lock:
            return self.player.is_playing() if self.player else False




import vlc
import threading
import time
from queue import Queue
from PyQt5.QtCore import QTimer


class AudioController:
    def __init__(self, ui_controller=None):
        self.ui_controller = ui_controller
        self.queue = Queue()
        self.queue2 = Queue()
        self.current_song = None
        self.current_file = None
        self.player = vlc.MediaPlayer()

        # Optional: set specific audio output device
        try:
            self.player.audio_output_set("alsa")
            self.player.audio_output_device_set("alsa", "hw:1,0")
            #self.player.audio_output_device_set(None, "hw:1,0")
        except Exception:
            pass

        self.lock = threading.Lock()
        self.skip_flag = threading.Event()
        self.paused_song = None

        # start playback loop in background
        self.thread = threading.Thread(target=self._playback_loop, daemon=True)
        self.thread.start()

    # ----------------------------------------------------------------------
    # Main playback loop
    # ----------------------------------------------------------------------
    def _playback_loop(self):
        while True:
            self.skip_flag.clear()
            filepath = self.queue.get()
            song = self.queue2.get()

            self.current_file = filepath
            self.current_song = song

            # ✅ safe UI updates on main thread
            if self.ui_controller:
                print("yes ui controller")
                #QTimer.singleShot(0, lambda s=song: self.ui_controller.update_song(s))
                self.ui_controller.update_song(self.current_song)
                #self.ui_controller.set_playing_state(True)
                self.ui_controller.update_queue(self.get_current_queue())
            else:
                print("no ui controller")

            # play file
            self._play_file(filepath)
            self._wait_until_finished()
            self.queue.task_done()

            if not self.skip_flag.is_set():
                self.current_song = None

            # ✅ update UI when playback finishes
            if self.ui_controller:
                QTimer.singleShot(0, lambda: self.ui_controller.set_playing_state(False))
                QTimer.singleShot(0, lambda: self.ui_controller.update_song(self.current_song))
                QTimer.singleShot(0, lambda: self.ui_controller.update_queue(self.get_current_queue()))

    # ----------------------------------------------------------------------
    # Helper methods
    # ----------------------------------------------------------------------
    def _play_file(self, filepath):
        with self.lock:
            media = vlc.Media(filepath)
            self.player.set_media(media)
            try:
                self.player.audio_output_set("alsa")
                self.player.audio_output_device_set("alsa", "hw:1,0")
                #self.player.audio_output_device_set(None, "hw:1,0")
            except Exception:
                pass
            self.player.play()
            print(f"Playing file: {filepath}")

    def _wait_until_finished(self):
        self.skip_flag.clear()
        started = False

        # wait up to 10s for playback to actually start
        for _ in range(100):
            if self.is_playing():
                started = True
                break
            time.sleep(0.1)
        if not started:
            return

        # update queue periodically while playing
        while self.is_playing() and not self.skip_flag.is_set():
            if self.ui_controller:
                self.ui_controller.update_queue(self.get_current_queue())
            time.sleep(0.2)

    def get_current_queue(self):
        with self.queue2.mutex:
            queue_list = list(self.queue2.queue)
            if self.current_song and self.current_song in queue_list:
                queue_list.remove(self.current_song)
            return queue_list

    # ----------------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------------
    def play(self, filepath, file_to_play):
        self.queue.put(filepath)
        self.queue2.put(file_to_play)
        print(f"Queued file: {file_to_play}")

    def stop(self):
        with self.lock:
            if self.player and self.player.is_playing():
                self.player.stop()
            with self.queue.mutex:
                self.queue.queue.clear()
                self.queue2.queue.clear()
        self.skip_flag.set()

    def pause(self):
        with self.lock:
            if self.player:
                self.paused_song = self.current_song
                try:
                    self.player.pause()
                except Exception:
                    pass

    def resume(self):
        with self.lock:
            if self.player:
                try:
                    self.player.play()
                    if self.ui_controller:
                        QTimer.singleShot(0, lambda: self.ui_controller.set_playing_state(True))
                        QTimer.singleShot(0, lambda s=self.paused_song: self.ui_controller.update_song(s))
                except Exception:
                    pass

    def skip(self):
        self.skip_flag.set()

    def is_playing(self):
        with self.lock:
            try:
                return self.player.is_playing() if self.player else False
            except Exception:
                return False

    def get_current_file(self):
        return self.current_file

    def get_queue_size(self):
        return self.queue.qsize()

    def get_queue_list(self):
        with self.queue.mutex:
            return list(self.queue.queue)

    def set_volume(self, volume):
        with self.lock:
            if self.player:
                try:
                    self.player.audio_set_volume(int(volume))
                except Exception:
                    pass

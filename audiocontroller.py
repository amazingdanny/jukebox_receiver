import vlc
import threading
import time
from queue import Queue
from uicontroller import UIController

class AudioController:
    def __init__(self, ui_controller : UIController):
        self.ui_controller = ui_controller
        self.queue = Queue()
        self.queue2 = Queue()
        self.current_song = None
        self.player = vlc.MediaPlayer()
        self.player.audio_output_set("alsa")
        self.player.audio_output_device_set(None, "alsa://hw:1,0")
        self.lock = threading.Lock()
        self.skip_flag = threading.Event()
        self.current_file = None
        self.thread = threading.Thread(target=self._playback_loop, daemon=True)
        self.thread.start()
        self.paused_song = None

    def _playback_loop(self):
        while True:
            self.skip_flag.clear()
            filepath = self.queue.get()
            song = self.queue2.get()
            #if self.ui_controller:
                #self.ui_controller.log_debug(f"Got from queue: {song} -> {filepath}")

            self.current_file = filepath
            self.current_song = song
            #if self.ui_controller:
                #self.ui_controller.log_debug(f"Set current_song = {self.current_song}")

            if self.ui_controller:
                self.ui_controller.set_playing_state(True)
                self.ui_controller.update_song(song)
                self.ui_controller.update_queue(self.get_current_queue())
            #self.ui_controller.log_connection(f"Now playing: {song}")
            self._play_file(filepath)
            self._wait_until_finished()
            #self.ui_controller.log_connection(f"Now stopping playing: {song}")
            #if self.ui_controller:
                #self.ui_controller.log_debug(f"Finished playing: {song}, skip={self.skip_flag.is_set()}")

            self.queue.task_done()

            if not self.skip_flag.is_set():
                self.current_song = None
                #if self.ui_controller:
                    #self.ui_controller.log_debug("Cleared current_song")

            if self.ui_controller:
                self.ui_controller.set_playing_state(False)
                self.ui_controller.update_song(self.current_song)
                self.ui_controller.update_queue(self.get_current_queue())

    def get_queue2_el(self):
        with self.queue2.mutex:
            # Return a copy without removing items
            queue_copy = list(self.queue2.queue)
            # Remove the first item if we're currently playing from the queue
            if queue_copy and queue_copy[0] == self.current_song:
                return queue_copy[1]  # Skip the currently playing song
            return queue_copy[0] if queue_copy else None

    def get_current_queue(self):
        with self.queue2.mutex:
            queue_list = list(self.queue2.queue)
            # Remove the currently playing song from queue display
            if self.current_song and self.current_song in queue_list:
                queue_list.remove(self.current_song)
            return queue_list

    def get_current_song(self):
        return self.current_song

    def _play_file(self, filepath):
        """Play a file - DO NOT STOP CURRENT PLAYBACK"""
        with self.lock:

            # NO STOP CALL HERE! Just load and play the new file
            media = vlc.Media(filepath)
            self.player.set_media(media)
            self.player.audio_output_set("alsa")
            self.player.audio_output_device_set(None, "hw:1,0")
            self.player.play()

    def _wait_until_finished(self):
        """Block until the current track actually starts and finishes."""
        self.skip_flag.clear()

        # Wait for VLC to start playback (it’s async)
        started = False
        for _ in range(100):  # up to ~10 seconds
            if self.is_playing():
                started = True
                break
            time.sleep(0.1)

        if not started:
            return  # avoid locking up the thread

        # Wait while it's playing
        while self.is_playing() and not self.skip_flag.is_set():
            if self.ui_controller:
                self.ui_controller.update_queue(self.get_current_queue())
            time.sleep(0.2)

        # Handle skip request or stop when finished

    def play(self, filepath, file_to_play):
        """Add a file to the queue."""
        self.queue.put(filepath)
        self.queue2.put(file_to_play)
        #if not self.is_playing():
            #self.current_song = file_to_play


    def stop(self):
        """Stop playback and clear queue."""
        with self.lock:
            if self.player and self.player.is_playing():
                self.player.stop()
            with self.queue.mutex:
                self.queue.queue.clear()
                self.queue2.queue.clear()
        self.skip_flag.set()

    def pause(self):
        """Pause current playback."""
        with self.lock:
            if self.player:
                self.paused_song = self.current_song
                self.player.pause()

    def resume(self):
        """Resume paused playback."""
        with self.lock:
            if self.player:
                self.player.play()
                self.ui_controller.set_playing_state(True)
                self.ui_controller.update_song(self.paused_song)

    def skip(self):
        """Skip the current song and move to the next one in the queue."""
        self.skip_flag.set()

    def is_playing(self):
        with self.lock:
            return self.player.is_playing() if self.player else False

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
                self.player.audio_set_volume(volume)
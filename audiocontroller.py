import os
import random
import vlc
import threading
import time
from queue import Queue
from kivy.clock import Clock, mainthread
from mutagen import File as MutagenFile


def get_album_art(filepath):
    """Return (image_bytes, mime_type) for the embedded cover art of `filepath`,
    or None if the file has no readable embedded artwork."""
    try:
        audio = MutagenFile(filepath)
    except Exception:
        return None
    if audio is None:
        return None

    try:
        # MP3 / ID3
        tags = getattr(audio, 'tags', None)
        if tags is not None and hasattr(tags, 'getall'):
            apic_frames = tags.getall('APIC')
            if apic_frames:
                pic = apic_frames[0]
                return pic.data, pic.mime

        # FLAC
        pictures = getattr(audio, 'pictures', None)
        if pictures:
            pic = pictures[0]
            return pic.data, pic.mime

        # MP4 / M4A
        if tags is not None and 'covr' in tags:
            covers = tags['covr']
            if covers:
                cover = covers[0]
                mime = 'image/png' if cover.imageformat == cover.FORMAT_PNG else 'image/jpeg'
                return bytes(cover), mime
    except Exception:
        pass

    return None


def get_artist(filepath):
    """Return the artist tag for `filepath`, or None if it has no readable artist metadata."""
    try:
        audio = MutagenFile(filepath, easy=True)
    except Exception:
        return None
    if audio is None or not getattr(audio, 'tags', None):
        return None

    for key in ('artist', 'albumartist'):
        try:
            value = audio.tags.get(key)
        except Exception:
            value = None
        if value:
            return value[0]

    return None


class AudioController:
    def __init__(self, ui_controller=None):
        self.ui_controller = ui_controller
        self.queue = Queue()
        self.queue2 = Queue()
        self.current_song = None
        self.display_song = None
        self.current_file = None
        self.player = vlc.MediaPlayer()

        # Optional: prefer ALSA output, but do not force a specific device
        try:
            self.player.audio_output_device_set("alsa", "hw:1,0")
        except Exception:
            pass

        self.volume = 20
        try:
            self.player.audio_set_volume(self.volume)
        except Exception:
            pass

        if self.ui_controller:
            self.ui_controller.update_volume(self.volume)


        self.lock = threading.Lock()
        self.skip_flag = threading.Event()
        self.paused_song = None
        self.is_paused = False  # Track pause state
        self._original_song = None  # Store clean song name before "Paused: " prefix
        self.display_song = None  # For displaying pause status

        # start playback loop in background
        self.thread = threading.Thread(target=self._playback_loop, daemon=True)
        self.thread.start()

    # ----------------------------------------------------------------------
    # Main playback loop
    # ----------------------------------------------------------------------
    def _playback_loop(self):
        while True:
            self.skip_flag.clear()
            self.is_paused = False
            filepath = self.queue.get()
            song = self.queue2.get()

            self.current_file = filepath
            self.current_song = song

            # ✅ safe UI updates on main thread using Kivy's mainthread decorator
            if self.ui_controller:
                print("yes ui controller")
                self.ui_controller.update_song(self.current_song)
                self.ui_controller.update_queue(self.get_current_queue())
                if hasattr(self.ui_controller, 'update_album_art'):
                    self.ui_controller.update_album_art(get_album_art(filepath))
                if hasattr(self.ui_controller, 'update_artist'):
                    self.ui_controller.update_artist(get_artist(filepath))
            else:
                print("no ui controller")

            # play file
            self._play_file(filepath)
            self.set_volume(self.volume)
            self._wait_until_finished()
            self.queue.task_done()

            if not self.skip_flag.is_set():
                self.current_song = "No song playing"

            # ✅ update UI when playback finishes
            if self.ui_controller:
                self.ui_controller.update_song(self.current_song)
                self.ui_controller.update_queue(self.get_current_queue())
                if self.current_song == "No song playing":
                    if hasattr(self.ui_controller, 'update_album_art'):
                        self.ui_controller.update_album_art(None)
                    if hasattr(self.ui_controller, 'update_artist'):
                        self.ui_controller.update_artist(None)

    # ----------------------------------------------------------------------
    # Helper methods
    # ----------------------------------------------------------------------
    def _play_file(self, filepath):
        with self.lock:
            # Stop any current playback first
            try:
                if self.player.is_playing():
                    self.player.stop()
                    time.sleep(0.2)  # Give VLC time to stop
            except Exception:
                pass
            
            # Create new media and set it
            media = vlc.Media(filepath)
            self.player.set_media(media)
            try:
                self.player.audio_output_set("alsa")
            except Exception:
                pass
            
            # Play with a small delay to ensure initialization
            time.sleep(0.1)
            self.player.play()
            try:
                self.player.audio_set_volume(self.volume)
            except Exception:
                pass
            print(f"Playing file: {filepath} at volume {self.volume}%")

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
            print(f"Playback never started for: {self.current_file}")
            return

        # update queue periodically while playing
        # Exit when playback stops and not paused, or when skip is pressed
        while not self.skip_flag.is_set():
            if self.is_paused:
                time.sleep(0.2)
                continue
            if not self.is_playing():
                break
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

    def handle_pause(self):
        if self.is_paused:
            self.resume()
        else:
            if self.player and self.player.is_playing():
                self.pause()

    def pause(self):
        with self.lock:
            if self.player:
                
                    # Store the ORIGINAL clean song name
                    self._original_song = self.current_song
                    # Remove any existing "Paused: " prefix
                    if self._original_song and self._original_song.startswith("Paused: "):
                        self._original_song = self._original_song.replace("Paused: ", "", 1)
                    
                    self.paused_song = self._original_song
                    # Set display version with "Paused: " prefix
                    self.display_song = f"Paused: {self._original_song}"
                    self.is_paused = True
                    
                    print(f"Paused. Original: {self._original_song}, Display: {self.display_song}")
                    
                    # Update UI to show paused state
                    if self.ui_controller:
                        self.ui_controller.update_song(self.display_song)
                    
                    try:
                        self.player.pause()
                    except Exception:
                        pass

    def resume(self):
        with self.lock:
            if self.player:
                try:
                    self.player.play()
                    self.is_paused = False
                    # Use the clean original song name
                    self.current_song = self._original_song
                    
                    print(f"Resumed. Current song: {self.current_song}")
                    
                    if self.ui_controller:
                        self.ui_controller.set_playing_state(True)
                        self.ui_controller.update_song(self.current_song)
                        self.ui_controller.update_queue(self.get_current_queue())
                        
                except Exception as e:
                    print(f"Error resuming: {e}")

    def skip(self):
        if self.queue.empty():
            self.current_song = "No song playing"
            self.stop()
        self.skip_flag.set()

    def clear_queue(self):
        with self.queue.mutex:
            self.queue.queue.clear()
            self.queue2.queue.clear()
    
    def play_random_song(self, usb_path):
        """Play one random audio file from the mounted USB path."""
        if not usb_path:
            print("USB path is required for random song playback.")
            return None

        song_files = self._find_audio_files(usb_path)
        if not song_files:
            print(f"No audio files found in USB path: {usb_path}")
            return None

        chosen_file = random.choice(song_files)
        chosen_name = os.path.basename(chosen_file)

        # Stop any current playback and clear queued songs before playing the random track
        self.stop()
        self.play(chosen_file, chosen_name)

        print(f"Playing random USB song: {chosen_name}")
        return chosen_file

    def queue_random_songs(self, usb_path, count=10):
        """Add a set of random audio files from the mounted USB path to the playback queue."""
        if not usb_path:
            print("USB path is required for random queue playback.")
            return []

        song_files = self._find_audio_files(usb_path)
        if not song_files:
            print(f"No audio files found in USB path: {usb_path}")
            return []

        # Use a shuffled list so we queue up to `count` unique random songs.
        chosen_files = random.sample(song_files, min(count, len(song_files)))

        # Keep current playback intact and queue the new random songs.
        queued_names = []
        for filepath in chosen_files:
            filename = os.path.basename(filepath)
            self.play(filepath, filename)
            queued_names.append(filename)

        print(f"Queued {len(queued_names)} random USB songs: {queued_names}")
        return chosen_files

    def _find_audio_files(self, directory):
        supported_extensions = (".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac")
        found_files = []

        for root, _, files in os.walk(directory):
            for name in files:
                if name.lower().endswith(supported_extensions):
                    found_files.append(os.path.join(root, name))

        return found_files

    def volume_up(self):
        self.set_volume(self.volume + 5)

    def volume_down(self):
        self.set_volume(self.volume - 5)

    def set_volume(self, volume):
        with self.lock:
            if self.player:
                volume = max(0, min(100, int(volume)))
                self.volume = volume
                try:
                    self.player.audio_set_volume(self.volume)
                except Exception:
                    pass
                if self.ui_controller:
                    self.ui_controller.update_volume(self.volume)

    def is_playing(self):
        with self.lock:
            try:
                return self.player.is_playing() if self.player else False
            except Exception:
                return False

    def get_progress(self):
        """Return (current_ms, total_ms) for the currently playing track, or (0, 0)
        if nothing is playing or VLC hasn't parsed the duration yet."""
        try:
            if not self.player or not self.player.is_playing():
                return 0, 0
            length = self.player.get_length()
            time = self.player.get_time()
            if length and length > 0 and time is not None and time >= 0:
                return time, length
        except Exception:
            pass
        return 0, 0

    def get_current_file(self):
        return self.current_file

    def get_queue_size(self):
        return self.queue.qsize()

    def get_queue_list(self):
        with self.queue.mutex:
            return list(self.queue.queue)



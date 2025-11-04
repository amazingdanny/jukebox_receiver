#!/usr/bin/env python3
import curses
import threading
import queue
import time
from evdev import InputDevice, ecodes
from datetime import datetime

# Touchscreen device - adjust if needed
TOUCH_DEVICE = '/dev/input/by-path/platform-3f204000.spi-cs-1-event'


class UIController:
    def __init__(self):
        #self.audio_controller = audio_controller
        self.current_song = "No song playing"
        self.queue = []
        self.volume = 50
        self.is_playing = False
        self.touch_manager = TouchscreenManager(TOUCH_DEVICE)
        self.ui_queue = queue.Queue()
        self.running = True

        # Socket connection logging
        self.connection_log = []
        self.message_log = []
        self.max_log_entries = 10  # Keep last 10 entries of each

    def start(self):
        """Start the UI in a separate thread"""
        self.thread = threading.Thread(target=self._ui_loop)
        self.thread.daemon = True
        self.thread.start()
        self.touch_manager.start_monitoring()
        print("UI Controller started")

    def stop(self):
        """Stop the UI"""
        self.running = False
        self.touch_manager.stop()

    def update_song(self, song_name):
        """Update the currently playing song"""
        self.current_song = song_name
        self.is_playing = True
        self._add_ui_event('song_changed')

    def update_queue(self, queue_list):
        """Update the queue list"""
        self.queue = queue_list[:5]  # Only show first 5 items
        self._add_ui_event('queue_updated')

    def update_volume(self, volume):
        """Update volume level"""
        self.volume = volume
        self._add_ui_event('volume_changed')

    def set_playing_state(self, playing):
        """Set playing/paused state"""
        self.is_playing = playing
        self._add_ui_event('state_changed')

    def log_debug(self, message: str):
        """Show debug messages inside the message log area"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"{timestamp} - [DEBUG] {message}"
        self.message_log.append(log_entry)
        if len(self.message_log) > self.max_log_entries:
            self.message_log.pop(0)
        self._add_ui_event('message_logged')

    def log_connection(self, address):
        """Log a new connection"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"{timestamp} - Connected: {address}"
        self.connection_log.append(log_entry)
        # Keep only recent entries
        if len(self.connection_log) > self.max_log_entries:
            self.connection_log.pop(0)
        self._add_ui_event('connection_logged')

    def log_message(self, message):
        """Log a received message"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"{timestamp} - Message: {message}"
        self.message_log.append(log_entry)
        # Keep only recent entries
        if len(self.message_log) > self.max_log_entries:
            self.message_log.pop(0)
        self._add_ui_event('message_logged')

    def _add_ui_event(self, event_type):
        """Add UI update event to queue"""
        self.ui_queue.put(event_type)

    def _ui_loop(self):
        """Main UI loop using curses"""
        curses.wrapper(self._main_ui)

    def _main_ui(self, stdscr):
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLUE)
        curses.init_pair(6, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
        curses.init_pair(7, curses.COLOR_WHITE, curses.COLOR_BLACK)

        curses.curs_set(0)
        stdscr.nodelay(1)
        stdscr.keypad(True)

        # Track previous UI state to avoid unnecessary redraws
        prev_state = {
            "song": None,
            "queue": None,
            "volume": None,
            "is_playing": None,
            "connection_log": [],
            "message_log": []
        }

        buttons = [
            {"label": " VOL- ", "action": "vol_down", "x": 0, "y": 0, "width": 8},
            {"label": " VOL+ ", "action": "vol_up", "x": 0, "y": 0, "width": 8},
            {"label": " PAUSE ", "action": "pause", "x": 0, "y": 0, "width": 8},
            {"label": " NEXT ", "action": "next", "x": 0, "y": 0, "width": 8},
            {"label": " CLEAR ", "action": "clear_logs", "x": 0, "y": 0, "width": 8},
        ]

        while self.running:
            height, width = stdscr.getmaxyx()

            # Only redraw when something changed
            if (self.current_song != prev_state["song"] or
                    self.queue != prev_state["queue"] or
                    self.volume != prev_state["volume"] or
                    self.is_playing != prev_state["is_playing"] or
                    self.connection_log != prev_state["connection_log"] or
                    self.message_log != prev_state["message_log"]):

                prev_state["song"] = self.current_song
                prev_state["queue"] = list(self.queue)
                prev_state["volume"] = self.volume
                prev_state["is_playing"] = self.is_playing
                prev_state["connection_log"] = list(self.connection_log)
                prev_state["message_log"] = list(self.message_log)

                stdscr.clear()

                # --- (Draw everything exactly like your original code) ---

                title = "RASPBERRY MUSIC PLAYER"
                stdscr.addstr(1, (width - len(title)) // 2, title, curses.color_pair(1) | curses.A_BOLD)

                status = "▶ PLAYING" if self.is_playing else "⏸ PAUSED"
                status_color = curses.color_pair(2) if self.is_playing else curses.color_pair(4)
                stdscr.addstr(3, (width - len(status)) // 2, status, status_color | curses.A_BOLD)

                song_display = f"Now Playing: {self.current_song}"
                stdscr.addstr(5, 2, song_display, curses.color_pair(2))

                vol_bar = "[" + "█" * (self.volume // 10) + " " * (10 - self.volume // 10) + "]"
                volume_display = f"Volume: {self.volume:3d}% {vol_bar}"
                stdscr.addstr(7, 2, volume_display, curses.color_pair(4))

                stdscr.addstr(9, 2, "Queue:", curses.A_BOLD)
                if self.queue:
                    for i, song in enumerate(self.queue):
                        stdscr.addstr(10 + i, 2, f"  {i + 1}. {song}", curses.color_pair(3))
                    queue_y = 10 + len(self.queue)
                else:
                    stdscr.addstr(10, 2, "  No songs in queue", curses.color_pair(4))
                    queue_y = 11

                # Connection logs
                stdscr.addstr(queue_y + 1, 2, "CONNECTIONS:", curses.color_pair(6) | curses.A_BOLD)
                for i, line in enumerate(reversed(self.connection_log[-5:])):
                    stdscr.addstr(queue_y + 2 + i, 2, f"  {line}", curses.color_pair(6))
                conn_y = queue_y + 2 + min(len(self.connection_log), 5)

                # Message logs
                stdscr.addstr(conn_y + 1, 2, "MESSAGES:", curses.color_pair(7) | curses.A_BOLD)
                for i, line in enumerate(reversed(self.message_log[-5:])):
                    truncated = line[:width - 4]
                    stdscr.addstr(conn_y + 2 + i, 2, f"  {truncated}", curses.color_pair(7))

                # Draw buttons
                button_spacing = width // (len(buttons) + 1)
                for i, button in enumerate(buttons):
                    button["x"] = button_spacing * (i + 1) - button["width"] // 2
                    button["y"] = height - 3
                    stdscr.addstr(button["y"], button["x"], button["label"], curses.color_pair(5) | curses.A_BOLD)

                stdscr.refresh()

            # ✅ Read touch/keyboard regardless of UI changes
            touch = self.touch_manager.get_touch_event()
            if touch:
                x, y = self._scale_touch_coordinates(touch[1], touch[2], width, height)
                for button in buttons:
                    if button["x"] <= x < button["x"] + button["width"] and button["y"] == y:
                        self._handle_button_press(button["action"])

            key = stdscr.getch()
            if key in [ord('q'), ord('Q')]:
                break

            time.sleep(0.05)

    def _scale_touch_coordinates(self, x, y, screen_width, screen_height):
        """Scale touch coordinates to screen coordinates"""
        touch_max_x = 4096
        touch_max_y = 4096

        x = max(0, min(x, touch_max_x))
        y = max(0, min(y, touch_max_y))

        scaled_x = int((x / touch_max_x) * screen_width)
        scaled_y = int((y / touch_max_y) * screen_height)

        return scaled_x, scaled_y

    def _handle_button_press(self, action):
        """Handle button press actions"""
        if action == 'vol_up':
            new_vol = min(100, self.volume + 10)
            #self.audio_controller.set_volume(new_vol)
            self.volume = new_vol
        elif action == 'vol_down':
            new_vol = max(0, self.volume - 10)
            #self.audio_controller.set_volume(new_vol)
            self.volume = new_vol
        elif action == 'pause':
            # Toggle play/pause
            self.is_playing = not self.is_playing
            #if self.is_playing:
                #self.audio_controller.resume()
            #else:
                #self.audio_controller.pause()
        elif action == 'next':
            # Skip to next song
            print("Next button pressed - implement skip functionality")
        elif action == 'clear_logs':
            # Clear all logs
            self.connection_log.clear()
            self.message_log.clear()
            print("Logs cleared")


class TouchscreenManager:
    def __init__(self, device_path):
        self.device_path = device_path
        self.touch_queue = queue.Queue()
        self.running = True
        self.last_x = 0
        self.last_y = 0

    def start_monitoring(self):
        self.thread = threading.Thread(target=self._monitor_touch)
        self.thread.daemon = True
        self.thread.start()

    def _monitor_touch(self):
        try:
            device = InputDevice(self.device_path)
            print(f"Touchscreen connected: {device.name}")

            for event in device.read_loop():
                if not self.running:
                    break

                if event.type == ecodes.EV_ABS:
                    if event.code == ecodes.ABS_X:
                        self.last_x = event.value
                    elif event.code == ecodes.ABS_Y:
                        self.last_y = event.value
                    elif event.code == ecodes.ABS_MT_POSITION_X:
                        self.last_x = event.value
                    elif event.code == ecodes.ABS_MT_POSITION_Y:
                        self.last_y = event.value

                elif event.type == ecodes.EV_KEY:
                    if event.code == ecodes.BTN_TOUCH:
                        if event.value == 1:  # Touch down
                            self.touch_queue.put(('touch', self.last_x, self.last_y))

        except Exception as e:
            print(f"Touchscreen error: {e}")

    def get_touch_event(self):
        try:
            return self.touch_queue.get_nowait()
        except queue.Empty:
            return None

    def stop(self):
        self.running = False
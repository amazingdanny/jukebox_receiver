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
        #print("UI Controller started")

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
        pass
        #"""Show debug messages inside the message log area"""
        #timestamp = datetime.now().strftime("%H:%M:%S")
        #log_entry = f"{timestamp} - [DEBUG] {message}"
        #self.message_log.append(log_entry)
        #if len(self.message_log) > self.max_log_entries:
            #self.message_log.pop(0)
        #self._add_ui_event('message_logged')

    def log_connection(self, address):
        pass
        #"""Log a new connection"""
        #timestamp = datetime.now().strftime("%H:%M:%S")
        #log_entry = f"{timestamp} - Connected: {address}"
        #self.connection_log.append(log_entry)
        # Keep only recent entries
        #if len(self.connection_log) > self.max_log_entries:
            #self.connection_log.pop(0)
        #self._add_ui_event('connection_logged')

    def log_message(self, message):
        pass
        """Log a received message"""
        #timestamp = datetime.now().strftime("%H:%M:%S")
        #log_entry = f"{timestamp} - Message: {message}"
        #self.message_log.append(log_entry)
        # Keep only recent entries
        #if len(self.message_log) > self.max_log_entries:
            #self.message_log.pop(0)
        #self._add_ui_event('message_logged')

    def _add_ui_event(self, event_type):
        """Add UI update event to queue"""
        self.ui_queue.put(event_type)

    def _ui_loop(self):
        """Main UI loop using curses"""
        curses.wrapper(self._main_ui)

    def _main_ui(self, stdscr):
        curses.start_color()
        curses.use_default_colors()

        curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)  # Title
        curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)  # Current Song
        curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)  # Queue
        curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLUE)  # Buttons

        curses.curs_set(0)
        stdscr.nodelay(1)
        stdscr.keypad(True)

        buttons = [
            {"label": "[ PREV ]", "action": "prev"},
            {"label": "[ PAUSE ]", "action": "pause"},
            {"label": "[ NEXT ]", "action": "next"},
            {"label": "[ VOL- ]", "action": "vol_down"},
            {"label": "[ VOL+ ]", "action": "vol_up"}
        ]

        while self.running:
            height, width = stdscr.getmaxyx()
            stdscr.erase()

            if height < 20 or width < 50:
                stdscr.addstr(0, 0, "Screen too small", curses.A_BOLD)
                stdscr.refresh()
                time.sleep(0.5)
                continue

            # Title
            title = "🎵 RASPBERRY MUSIC PLAYER 🎵"
            stdscr.addstr(1, (width - len(title)) // 2, title, curses.color_pair(1) | curses.A_BOLD)

            # --- Current Song Box ---
            box_width = width // 2
            box_height = 5
            box_x = (width - box_width) // 2
            box_y = 4

            # Draw border
            try:
                for x in range(box_x, box_x + box_width):
                    stdscr.addch(box_y, x, curses.ACS_HLINE)
                    stdscr.addch(box_y + box_height, x, curses.ACS_HLINE)
                for y in range(box_y, box_y + box_height + 1):
                    stdscr.addch(y, box_x, curses.ACS_VLINE)
                    stdscr.addch(y, box_x + box_width, curses.ACS_VLINE)
                stdscr.addch(box_y, box_x, curses.ACS_ULCORNER)
                stdscr.addch(box_y, box_x + box_width, curses.ACS_URCORNER)
                stdscr.addch(box_y + box_height, box_x, curses.ACS_LLCORNER)
                stdscr.addch(box_y + box_height, box_x + box_width, curses.ACS_LRCORNER)
            except curses.error:
                pass

            # Song status text inside box
            status = "PLAYING" if self.is_playing else "PAUSED"
            song_display = self.current_song or "No song playing"
            song_display = song_display[:box_width - 4]  # Trim for long names

            stdscr.addstr(box_y + 1, box_x + 2, f"Status: {status}", curses.color_pair(2) | curses.A_BOLD)
            stdscr.addstr(box_y + 2, box_x + 2, f"Now Playing:", curses.A_BOLD)
            stdscr.addstr(box_y + 3, box_x + 2, song_display, curses.color_pair(2) | curses.A_BOLD)

            # --- Queue Section (Left) ---
            queue_y = box_y + box_height + 2
            stdscr.addstr(queue_y, 2, "Next Up:", curses.color_pair(3) | curses.A_BOLD)
            if self.queue:
                for i, song in enumerate(self.queue[:5]):
                    display = f"{i + 1}. {song}"
                    stdscr.addstr(queue_y + i + 1, 2, display[:width // 3], curses.color_pair(3))
            else:
                stdscr.addstr(queue_y + 1, 2, "No songs", curses.color_pair(3))

            # --- Buttons (Centered Below Song Box) ---
            btn_y = box_y + box_height + 6
            total_len = sum(len(b["label"]) for b in buttons) + (len(buttons) - 1) * 3
            start_x = (width - total_len) // 2

            x = start_x
            for b in buttons:
                stdscr.addstr(btn_y, x, b["label"], curses.color_pair(5) | curses.A_BOLD)
                b["x"], b["y"], b["width"] = x, btn_y, len(b["label"])
                x += len(b["label"]) + 3

            stdscr.refresh()
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
            pass
        elif action == 'clear_logs':
            # Clear all logs
            self.connection_log.clear()
            self.message_log.clear()


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
            #print(f"Touchscreen connected: {device.name}")

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
            pass

    def get_touch_event(self):
        try:
            return self.touch_queue.get_nowait()
        except queue.Empty:
            return None

    def stop(self):
        self.running = False
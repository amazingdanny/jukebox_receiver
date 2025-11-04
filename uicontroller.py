#!/usr/bin/env python3
import curses
import threading
import queue
import time
from evdev import InputDevice, ecodes
from datetime import datetime

# Touchscreen device path - adjust if needed
TOUCH_DEVICE = '/dev/input/by-path/platform-3f204000.spi-cs-1-event'


class UIController:
    def __init__(self, audio_controller=None):
        self.audio_controller = audio_controller

        # Visible state
        self.current_song = "No song playing"
        self.queue = []
        self.volume = 50
        self.is_playing = False

        # Touch manager
        self.touch_manager = TouchscreenManager(TOUCH_DEVICE)

        # Control
        self.running = True
        self.ui_queue = queue.Queue()

        # Button definitions (labels and actions)
        self.buttons = [
            {"label": "  PREV  ", "action": "prev"},
            {"label": "  PLAY  ", "action": "pause"},  # toggle play/pause
            {"label": "  NEXT  ", "action": "next"},
            {"label": "  VOL-  ", "action": "vol_down"},
            {"label": "  STOP  ", "action": "stop"},
            {"label": "  VOL+  ", "action": "vol_up"},
        ]

        # pressed button name for visual feedback
        self._pressed_button = None

    # ---------------- Public API (kept same) ----------------
    def start(self):
        """Start UI loop in separate thread."""
        self.thread = threading.Thread(target=self._ui_loop, daemon=True)
        self.thread.start()
        self.touch_manager.start_monitoring()

    def stop(self):
        """Stop UI & touch monitoring."""
        self.running = False
        self.touch_manager.stop()

    def update_song(self, song_name):
        """Update currently playing song (called by AudioController)."""
        self.current_song = song_name
        self.is_playing = True
        # notify ui loop (optional)
        try:
            self.ui_queue.put_nowait('redraw')
        except Exception:
            pass

    def update_queue(self, queue_list):
        """Update the visible queue (keeps first N)."""
        # copy-slice to keep UI small
        self.queue = list(queue_list)[:20]
        try:
            self.ui_queue.put_nowait('redraw')
        except Exception:
            pass

    def update_volume(self, vol):
        self.volume = vol
        try:
            self.ui_queue.put_nowait('redraw')
        except Exception:
            pass

    def set_playing_state(self, playing: bool):
        self.is_playing = playing
        try:
            self.ui_queue.put_nowait('redraw')
        except Exception:
            pass

    # ---------------- Internal UI loop ----------------
    def _ui_loop(self):
        """Start curses wrapper and run _main_ui."""
        # Silence stdout/stderr to avoid prints showing up under curses
        import sys
        # keep commented-out lines if you prefer to capture logs to file
        # sys.stdout = open('/dev/null', 'w')
        # sys.stderr = open('/dev/null', 'w')
        curses.wrapper(self._main_ui)

    # helper to draw safely (clip)
    def _safe_addstr(self, win, y, x, text, attr=0):
        if y < 0:
            return
        h, w = win.getmaxyx()
        if x >= w:
            return
        maxlen = w - x
        if maxlen <= 0:
            return
        clipped = text[:maxlen]
        try:
            win.addstr(y, x, clipped, attr)
        except curses.error:
            pass

    def _main_ui(self, stdscr):
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)      # title / borders
        curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)    # now playing text
        curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)   # queue
        curses.init_pair(4, curses.COLOR_CYAN, curses.COLOR_BLACK)     # status
        curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLUE)     # buttons normal
        curses.init_pair(6, curses.COLOR_BLACK, curses.COLOR_WHITE)    # buttons pressed (invert)
        curses.init_pair(7, curses.COLOR_WHITE, curses.COLOR_BLACK)    # generic

        curses.curs_set(0)
        stdscr.nodelay(1)
        stdscr.keypad(True)

        # compute dynamic sizes every frame
        prev_state = {
            "song": None,
            "queue": None,
            "is_playing": None,
            "volume": None
        }

        # main loop
        while self.running:
            h, w = stdscr.getmaxyx()
            stdscr.erase()

            # Minimum safety
            if h < 16 or w < 40:
                self._safe_addstr(stdscr, 0, 0, "Screen too small for UI", curses.A_BOLD)
                stdscr.refresh()
                time.sleep(0.3)
                continue

            # Title
            title = " RASPBERRY MUSIC PLAYER "
            self._safe_addstr(stdscr, 1, max(1, (w - len(title)) // 2), title, curses.color_pair(1) | curses.A_BOLD)

            # Status
            status_text = "▶ PLAYING" if self.is_playing else "⏸ PAUSED"
            status_attr = curses.color_pair(4) | curses.A_BOLD
            self._safe_addstr(stdscr, 3, max(1, (w - len(status_text)) // 2), status_text, status_attr)

            # BIG Now Playing box (use most of top area)
            box_w = min(w - 8, max(40, w - 12))
            box_h = max(5, int(h * 0.25))  # larger vertical size
            box_x = max(2, (w - box_w) // 2)
            box_y = 5

            # draw box border
            try:
                box_win = curses.newwin(box_h, box_w, box_y, box_x)
                box_win.box()
                box_title = " NOW PLAYING "
                try:
                    box_win.addstr(0, max(2, (box_w - len(box_title)) // 2), box_title, curses.color_pair(1) | curses.A_BOLD)
                except curses.error:
                    pass

                # display status inside box
                status_inside = "PLAYING" if self.is_playing else "PAUSED"
                try:
                    box_win.addstr(1, 2, f"Status: {status_inside}", curses.color_pair(7) | curses.A_BOLD)
                except curses.error:
                    pass

                # large song text center-line
                song_text = str(self.current_song or "No song playing")
                max_song_len = box_w - 8
                if len(song_text) > max_song_len:
                    song_text = song_text[:max_song_len - 3] + "..."
                # center vertically
                mid_y = box_h // 2
                try:
                    box_win.addstr(mid_y, max(2, (box_w - len(song_text)) // 2), song_text,
                                   curses.color_pair(2) | curses.A_BOLD)
                except curses.error:
                    pass

                box_win.noutrefresh()
            except curses.error:
                # fallback inline if newwin fails
                self._safe_addstr(stdscr, box_y + 1, box_x + 2, f"Now Playing: {self.current_song}", curses.color_pair(2))

            # Buttons section: larger spacing and two rows
            btn_gap = 4
            top_row = self.buttons[:3]
            bot_row = self.buttons[3:]

            def row_width(btns, gap=btn_gap):
                return sum(len(b["label"]) + 4 for b in btns) + gap * (len(btns) - 1)

            # choose area under the box
            btn_area_y = box_y + box_h + 1
            # draw the top row
            r1_w = row_width(top_row, btn_gap)
            start_x_r1 = max(2, (w - r1_w) // 2)
            x = start_x_r1
            for b in top_row:
                label = f"  {b['label']}  "
                # ensure fit
                if x + len(label) >= w - 2:
                    label = label[:max(3, w - 2 - x)]
                # if pressed, use invert color
                if self._pressed_button == b["action"]:
                    attr = curses.color_pair(6) | curses.A_BOLD
                else:
                    attr = curses.color_pair(5) | curses.A_BOLD
                self._safe_addstr(stdscr, btn_area_y, x, label, attr)
                # store button bbox (two rows tolerance)
                b["x"], b["y"], b["w"], b["h"] = x, btn_area_y, len(label), 1
                x += len(label) + btn_gap

            # draw bottom row
            r2_w = row_width(bot_row, btn_gap)
            start_x_r2 = max(2, (w - r2_w) // 2)
            x = start_x_r2
            for b in bot_row:
                label = f"  {b['label']}  "
                if x + len(label) >= w - 2:
                    label = label[:max(3, w - 2 - x)]
                if self._pressed_button == b["action"]:
                    attr = curses.color_pair(6) | curses.A_BOLD
                else:
                    attr = curses.color_pair(5) | curses.A_BOLD
                self._safe_addstr(stdscr, btn_area_y + 3, x, label, attr)
                b["x"], b["y"], b["w"], b["h"] = x, btn_area_y + 3, len(label), 1
                x += len(label) + btn_gap

            # Separator under buttons
            sep_y = btn_area_y + 5
            if sep_y < h - 4:
                try:
                    stdscr.hline(sep_y, 2, curses.ACS_HLINE, w - 4)
                except curses.error:
                    pass

            # Queue area - fills remaining lower area
            q_y = sep_y + 1
            q_h = h - q_y - 2
            q_w = w - 6
            q_x = 3
            try:
                qwin = curses.newwin(q_h, q_w, q_y, q_x)
                qwin.box()
                qtitle = " NEXT UP "
                try:
                    qwin.addstr(0, 2, qtitle, curses.color_pair(1) | curses.A_BOLD)
                except curses.error:
                    pass
                # list queue items with larger spacing
                display_count = min(len(self.queue), q_h - 2)
                for i in range(display_count):
                    item = f"{i+1}. {self.queue[i]}"
                    if len(item) > q_w - 4:
                        item = item[:q_w - 7] + "..."
                    try:
                        qwin.addstr(1 + i, 2, item, curses.color_pair(3) | curses.A_BOLD)
                    except curses.error:
                        pass
                qwin.noutrefresh()
            except curses.error:
                # fallback
                self._safe_addstr(stdscr, q_y, q_x, "Next Up:", curses.color_pair(3) | curses.A_BOLD)
                for i, s in enumerate(self.queue[:max(1, q_h - 2)]):
                    self._safe_addstr(stdscr, q_y + 1 + i, q_x + 2, f"{i+1}. {s}", curses.color_pair(3))

            # do a batch refresh to avoid flicker
            curses.doupdate()

            # Touch handling: map touch to button bounding boxes (allow small vertical tolerance)
            t = self.touch_manager.get_touch_event()
            if t and t[0] == 'touch' and len(t) == 3:
                _, tx, ty = t
                sx, sy = self._scale_touch_coordinates(tx, ty, w, h)
                # find which button was pressed
                pressed_action = None
                for b in self.buttons:
                    bx, by, bw, bh = b.get("x", 0), b.get("y", 0), b.get("w", 0), b.get("h", 1)
                    if bx <= sx < bx + bw and (by - 1) <= sy <= (by + bh + 1):
                        pressed_action = b["action"]
                        break
                if pressed_action:
                    # visually show press
                    self._pressed_button = pressed_action
                    # redraw immediate pressed state
                    curses.doupdate()
                    # call action handler
                    self._handle_button_press(pressed_action)
                    # tiny feedback delay
                    time.sleep(0.12)
                    self._pressed_button = None

            # Keyboard handling (same bindings)
            try:
                key = stdscr.getch()
                if key in [ord('q'), ord('Q')]:
                    self.running = False
                    break
                elif key == ord(' '):
                    self._handle_button_press('pause')
                elif key == ord('+') or key == ord('='):
                    self._handle_button_press('vol_up')
                elif key == ord('-'):
                    self._handle_button_press('vol_down')
                elif key == ord('n'):
                    self._handle_button_press('next')
                elif key == ord('s'):
                    self._handle_button_press('stop')
            except curses.error:
                pass

            # small sleep to reduce CPU usage
            time.sleep(0.06)

    # ----------------- Button action mapping -----------------
    def _handle_button_press(self, action):
        # map actions to audio_controller if provided
        if action == 'prev':
            # user should implement prev logic if desired
            if self.audio_controller:
                try:
                    self.audio_controller.skip()  # or implement prev
                except Exception:
                    pass
        elif action == 'pause':
            # toggle play/pause
            self.is_playing = not self.is_playing
            if self.audio_controller:
                try:
                    if self.is_playing:
                        self.audio_controller.resume()
                    else:
                        self.audio_controller.pause()
                except Exception:
                    pass
        elif action == 'next':
            if self.audio_controller:
                try:
                    self.audio_controller.skip()
                except Exception:
                    pass
        elif action == 'vol_down':
            self.volume = max(0, self.volume - 10)
            if self.audio_controller:
                try:
                    self.audio_controller.set_volume(self.volume)
                except Exception:
                    pass
        elif action == 'vol_up':
            self.volume = min(100, self.volume + 10)
            if self.audio_controller:
                try:
                    self.audio_controller.set_volume(self.volume)
                except Exception:
                    pass
        elif action == 'stop':
            if self.audio_controller:
                try:
                    self.audio_controller.stop()
                except Exception:
                    pass

    # ----------------- Touch coordinate helper -----------------
    def _scale_touch_coordinates(self, x, y, screen_width, screen_height):
        """Scale touch coordinates (0..touch_max) to screen cols/rows."""
        touch_max_x = 4096
        touch_max_y = 4096
        x = max(0, min(x, touch_max_x))
        y = max(0, min(y, touch_max_y))
        scaled_x = int((x / touch_max_x) * screen_width)
        scaled_y = int((y / touch_max_y) * screen_height)
        return scaled_x, scaled_y


class TouchscreenManager:
    def __init__(self, device_path):
        self.device_path = device_path
        self.touch_queue = queue.Queue()
        self.running = True
        self.last_x = 0
        self.last_y = 0

    def start_monitoring(self):
        self.thread = threading.Thread(target=self._monitor_touch, daemon=True)
        self.thread.start()

    def _monitor_touch(self):
        try:
            device = InputDevice(self.device_path)
        except Exception:
            # If the device doesn't exist, keep running without touch
            return

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
                    if event.value == 1:  # touch down
                        # put a copy to avoid blocking
                        try:
                            self.touch_queue.put_nowait(('touch', self.last_x, self.last_y))
                        except queue.Full:
                            pass

    def get_touch_event(self):
        try:
            return self.touch_queue.get_nowait()
        except queue.Empty:
            return None

    def stop(self):
        self.running = False

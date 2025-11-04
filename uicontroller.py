# Replace your UIController with this — TouchscreenManager stays the same.
import curses
import threading
import queue
import time
from evdev import InputDevice, ecodes

TOUCH_DEVICE = '/dev/input/by-path/platform-3f204000.spi-cs-1-event'

class UIController:
    def __init__(self, audio_controller=None):
        self.audio_controller = audio_controller
        self.current_song = "No song playing"
        self.queue = []
        self.volume = 50
        self.is_playing = False

        self.touch_manager = TouchscreenManager(TOUCH_DEVICE)
        self.running = True
        self.ui_queue = queue.Queue()

        # buttons config (labels are larger to simulate "bigger" UI)
        self.buttons = [
            {"label": "  PREV  ", "action": "prev"},
            {"label": "  PLAY  ", "action": "pause"},
            {"label": "  NEXT  ", "action": "next"},
            {"label": "  VOL-  ", "action": "vol_down"},
            {"label": "  STOP  ", "action": "stop"},
            {"label": "  VOL+  ", "action": "vol_up"},
        ]

        self._pressed_button = None
        # Keep previous-state to decide when to update
        self._prev_song = None
        self._prev_queue = None
        self._prev_playing = None
        self._static_drawn = False

    def start(self):
        self.thread = threading.Thread(target=self._ui_loop, daemon=True)
        self.thread.start()
        self.touch_manager.start_monitoring()

    def stop(self):
        self.running = False
        self.touch_manager.stop()

    # external callers call these
    def update_song(self, song):
        self.current_song = song
        try:
            self.ui_queue.put_nowait('song')
        except Exception:
            pass

    def update_queue(self, queue_list):
        # keep entire queue state, but UI will only display next 3
        self.queue = list(queue_list)
        try:
            self.ui_queue.put_nowait('queue')
        except Exception:
            pass

    def set_playing_state(self, playing):
        self.is_playing = playing
        try:
            self.ui_queue.put_nowait('status')
        except Exception:
            pass

    def set_volume(self, vol):
        self.volume = vol
        try:
            self.ui_queue.put_nowait('volume')
        except Exception:
            pass

    # safe draw helper
    def _safe_addstr(self, win, y, x, text, attr=0):
        if y < 0:
            return
        h, w = win.getmaxyx()
        if x >= w:
            return
        maxlen = w - x
        if maxlen <= 0:
            return
        try:
            win.addstr(y, x, text[:maxlen], attr)
        except curses.error:
            pass

    def _ui_loop(self):
        curses.wrapper(self._main_ui)

    def _draw_static(self, stdscr, dims):
        """Draw static UI elements once: borders, boxes, and button outlines."""
        h, w = dims
        stdscr.erase()
        stdscr.border()

        title = " RASPBERRY MUSIC PLAYER "
        self._safe_addstr(stdscr, 1, max(1, (w - len(title)) // 2), title, curses.color_pair(1) | curses.A_BOLD)

        # --- Move Now Playing box slightly higher to free space below ---
        box_w = min(w - 8, max(40, w - 12))
        box_h = max(5, int(h * 0.22))        # slightly smaller to free more space
        box_x = max(2, (w - box_w) // 2)
        box_y = 2                            # moved higher (was 4)

        # create and draw box window
        try:
            box_win = curses.newwin(box_h, box_w, box_y, box_x)
            box_win.box()
            box_title = " NOW PLAYING "
            self._safe_addstr(box_win, 0, max(2, (box_w - len(box_title)) // 2), box_title, curses.color_pair(1) | curses.A_BOLD)
            box_win.noutrefresh()
        except curses.error:
            pass

        # Buttons area: compute two rows and draw them (but not pressed state)
        # --- Reduce spacing between buttons ---
        btn_gap = 2                          # reduced gap (was 4)
        top_row = self.buttons[:3]
        bot_row = self.buttons[3:]

        def row_width(btns, gap=btn_gap):
            return sum(len(b["label"]) + 4 for b in btns) + gap * (len(btns) - 1)

        # place buttons closer to the box
        btn_area_y = box_y + box_h         # reduced vertical gap (was +1/+3 originally)
        # top row
        r1_w = row_width(top_row)
        start_x_r1 = max(2, (w - r1_w) // 2)
        x = start_x_r1
        for b in top_row:
            label = f"  {b['label']}  "
            self._safe_addstr(stdscr, btn_area_y, x, label, curses.color_pair(5) | curses.A_BOLD)
            b["x"], b["y"], b["w"], b["h"] = x, btn_area_y, len(label), 1
            x += len(label) + btn_gap

        # bottom row (closer)
        r2_w = row_width(bot_row)
        start_x_r2 = max(2, (w - r2_w) // 2)
        x = start_x_r2
        for b in bot_row:
            label = f"  {b['label']}  "
            self._safe_addstr(stdscr, btn_area_y + 2, x, label, curses.color_pair(5) | curses.A_BOLD)  # smaller vertical offset
            b["x"], b["y"], b["w"], b["h"] = x, btn_area_y + 2, len(label), 1
            x += len(label) + btn_gap

        # separator
        sep_y = btn_area_y + 4
        if sep_y < h - 4:
            try:
                stdscr.hline(sep_y, 2, curses.ACS_HLINE, w - 4)
            except curses.error:
                pass

        # queue box (static) — place it higher so it's visible
        q_y = sep_y + 1
        # reserve minimal height so queue box always visible even with big fonts
        q_h = max(4, h - q_y - 2)
        q_w = w - 6
        q_x = 3
        try:
            qwin = curses.newwin(q_h, q_w, q_y, q_x)
            qwin.box()
            qtitle = " NEXT UP "
            self._safe_addstr(qwin, 0, 2, qtitle, curses.color_pair(1) | curses.A_BOLD)
            qwin.noutrefresh()
        except curses.error:
            pass

        # finally flush static
        curses.doupdate()
        # store static dims used later
        # note: keep the same tuple length as your other code expects
        self._static_dims = (box_x, box_y, box_w, box_h, q_x, q_y, q_w, q_h, btn_area_y)
        self._static_drawn = True

    def _update_song_area(self, stdscr, dims):
        """Update only song text and status inside the box if it changed."""
        box_x, box_y, box_w, box_h, *_ = dims
        try:
            box_win = curses.newwin(box_h, box_w, box_y, box_x)
            box_win.box()
            box_title = " NOW PLAYING "
            self._safe_addstr(box_win, 0, max(2, (box_w - len(box_title)) // 2), box_title, curses.color_pair(1) | curses.A_BOLD)

            status_inside = "PLAYING" if self.is_playing else "PAUSED"
            self._safe_addstr(box_win, 1, 2, f"Status: {status_inside}", curses.color_pair(7) | curses.A_BOLD)

            # Draw song text (no shadow)
            song_text = str(self.current_song or "No song playing")
            max_song_len = box_w - 8
            if len(song_text) > max_song_len:
                song_text = song_text[:max_song_len - 3] + "..."
            mid_y = box_h // 2
            self._safe_addstr(box_win, mid_y, max(2, (box_w - len(song_text)) // 2), song_text, curses.color_pair(2) | curses.A_BOLD)

            box_win.noutrefresh()
        except curses.error:
            pass

    def _update_queue_area(self, stdscr, dims):
        """Update only the queue window contents — show only next 3 items."""
        _, _, _, _, q_x, q_y, q_w, q_h, _ = dims
        try:
            qwin = curses.newwin(q_h, q_w, q_y, q_x)
            qwin.box()
            qtitle = " NEXT UP "
            self._safe_addstr(qwin, 0, 2, qtitle, curses.color_pair(1) | curses.A_BOLD)
            # show only the next 3 songs to fit larger fonts
            display_count = min(3, q_h - 2)
            for i in range(display_count):
                if i < len(self.queue):
                    item = f"{i+1}. {self.queue[i]}"
                else:
                    item = ""
                if len(item) > q_w - 4:
                    item = item[:q_w - 7] + "..."
                # use slightly smaller spacing for queue items
                self._safe_addstr(qwin, 1 + i, 2, item, curses.color_pair(3) | curses.A_BOLD)
            # clear remaining visible lines (if queue shrank)
            for j in range(display_count, q_h - 2):
                self._safe_addstr(qwin, 1 + j, 2, " " * (q_w - 4))
            qwin.noutrefresh()
        except curses.error:
            pass

    def _redraw_button(self, stdscr, b):
        """Redraw a single button (used for pressed highlight)."""
        x, y, w = b.get("x", 0), b.get("y", 0), b.get("w", 0)
        label = f"  {b['label']}  "
        if self._pressed_button == b["action"]:
            attr = curses.color_pair(6) | curses.A_BOLD
        else:
            attr = curses.color_pair(5) | curses.A_BOLD
        self._safe_addstr(stdscr, y, x, label[:w], attr)
        stdscr.noutrefresh()

    def _main_ui(self, stdscr):
        # initialize colors & curses options
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLUE)
        curses.init_pair(6, curses.COLOR_BLACK, curses.COLOR_WHITE)
        curses.init_pair(7, curses.COLOR_WHITE, curses.COLOR_BLACK)

        curses.curs_set(0)
        stdscr.nodelay(1)
        stdscr.keypad(True)

        # main loop
        while self.running:
            h, w = stdscr.getmaxyx()

            # safety check
            if h < 12 or w < 40:
                stdscr.erase()
                self._safe_addstr(stdscr, 0, 0, "Screen too small for UI", curses.A_BOLD)
                stdscr.refresh()
                time.sleep(0.3)
                continue

            # draw static UI once (borders, boxes, buttons)
            if not self._static_drawn:
                self._draw_static(stdscr, (h, w))

            dims = self._static_dims

            # update song area only if changed
            if self.current_song != self._prev_song or self.is_playing != self._prev_playing:
                self._update_song_area(stdscr, dims)
                self._prev_song = self.current_song
                self._prev_playing = self.is_playing

            # update queue only if changed
            if self.queue != self._prev_queue:
                self._update_queue_area(stdscr, dims)
                self._prev_queue = list(self.queue)

            # if a pressed button is set, redraw only that button for feedback
            if self._pressed_button:
                for b in self.buttons:
                    if b["action"] == self._pressed_button:
                        self._redraw_button(stdscr, b)
                        break
            else:
                # ensure normal button appearance if nothing pressed
                # redraw all buttons once per loop if any previous pressed cleared
                for b in self.buttons:
                    self._redraw_button(stdscr, b)

            # flush batched updates
            curses.doupdate()

            # handle touch event: map touch coords to button boxes
            t = self.touch_manager.get_touch_event()
            if t and t[0] == 'touch' and len(t) == 3:
                _, tx, ty = t
                sx, sy = self._scale_touch_coordinates(tx, ty, w, h)
                pressed_action = None
                # search button bbox
                for b in self.buttons:
                    bx, by, bw, bh = b.get("x", 0), b.get("y", 0), b.get("w", 0), b.get("h", 1)
                    if bx <= sx < bx + bw and (by - 1) <= sy <= (by + bh + 1):
                        pressed_action = b["action"]
                        break
                if pressed_action:
                    # set highlight, redraw that button only
                    self._pressed_button = pressed_action
                    # immediate visual feedback
                    for b in self.buttons:
                        if b["action"] == pressed_action:
                            self._redraw_button(stdscr, b)
                            curses.doupdate()
                            break
                    # perform action
                    self._handle_button_press(pressed_action)
                    time.sleep(0.12)
                    # clear highlight
                    self._pressed_button = None
                    # redraw that button to normal
                    for b in self.buttons:
                        if b["action"] == pressed_action:
                            self._redraw_button(stdscr, b)
                            curses.doupdate()
                            break

            # keyboard handling preserved
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

            time.sleep(0.06)

    # keep actions as before
    def _handle_button_press(self, action):
        if action == 'prev':
            if self.audio_controller:
                try:
                    self.audio_controller.skip()  # or implement prev
                except Exception:
                    pass
        elif action == 'pause':
            self.is_playing = not self.is_playing
            if self.audio_controller:
                try:
                    if self.is_playing:
                        self.audio_controller.resume()
                    else:
                        self.audio_controller.pause()
                except Exception:
                    pass
            # queue a redraw for status
            try:
                self.ui_queue.put_nowait('status')
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

    def _scale_touch_coordinates(self, x, y, screen_width, screen_height):
        touch_max_x = 4096
        touch_max_y = 4096
        x = max(0, min(x, touch_max_x))
        y = max(0, min(y, touch_max_y))
        sx = int((x / touch_max_x) * screen_width)
        sy = int((y / touch_max_y) * screen_height)
        return sx, sy

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
            # no touch device available
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
                if event.code == ecodes.BTN_TOUCH and event.value == 1:
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
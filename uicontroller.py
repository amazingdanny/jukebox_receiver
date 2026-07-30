

import logging
from typing import List, Optional
import os

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.config import Config
from kivy.core.window import Window
from kivy.core.window import Window
from kivy.core.text import LabelBase
from kivy.clock import Clock, mainthread
from kivy.graphics import Color, Rectangle

#Window.fullscreen = 'fake'
#Window.size = (1920, 1080)
def show_size(dt):
    print("Window size:", Window.size)
    print("Window system size:", Window.system_size)

Clock.schedule_once(show_size, 2)

log = logging.getLogger("kivy_ui")
logging.basicConfig(level=logging.INFO)


class MusicPlayerUI(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = 15
        self.spacing = 10
        
        self.current_song = "No song playing"
        self.ui_controller = None
        self.is_paused = False
        self.cpu_temp_label = None
        self.connection_status_label = None

        # Set background color
        with self.canvas.before:
            Color(0.05, 0.05, 0.05, 1)  # Dark background
            self.bg_rect = Rectangle(size=Window.size, pos=self.pos)
            self.bind(pos=self._update_rect, size=self._update_rect)
        
        self._build_ui()
        self.update_song(self.current_song)
        Clock.schedule_interval(self._update_cpu_temp, 1)
        self._update_cpu_temp(0)

    def _update_rect(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size

    def _build_ui(self):
        # Top header row with title and CPU temperature
        header = BoxLayout(orientation='horizontal', size_hint_y=0.12, spacing=10)

        title = Label(
            text="♫ Music Player ♫",
            font_size='24sp',
            color=(0.2, 0.8, 1, 1),  # Bright cyan
            bold=True,
            halign='left',
            valign='middle'
        )
        title.bind(size=self._update_label_text_size)
        header.add_widget(title)

        self.cpu_temp_label = Label(
            text="CPU: --°C",
            font_size='16sp',
            color=(1, 1, 1, 1),
            size_hint_x=0.35,
            halign='right',
            valign='middle'
        )
        self.cpu_temp_label.bind(size=self._update_label_text_size)
        header.add_widget(self.cpu_temp_label)

        self.connection_status_label = Label(
            text='● Disconnected',
            font_size='16sp',
            color=(0.95, 0.2, 0.2, 1),
            size_hint_x=0.22,
            halign='right',
            valign='middle'
        )
        self.connection_status_label.bind(size=self._update_label_text_size)
        header.add_widget(self.connection_status_label)

        self.add_widget(header)

        # Current song label with styling
        self.song_label = Label(
            text=f"Now Playing:\n{self.current_song}",
            font_size='18sp',
            size_hint_y=0.25,
            color=(0.2, 1, 0.5, 1),  # Bright green
            bold=True,
            text_size=(Window.width - 30, None),
            halign='center',
            valign='middle'
        )
        self.add_widget(self.song_label)

        # Control buttons layout
        controls = BoxLayout(orientation='horizontal', size_hint_y=0.12, spacing=10, padding=5)
        
        pause_btn = Button(
            text='⏸ Pause / Resume',
            size_hint_x=0.5,
            background_color=(1, 0.5, 0, 1),  # Orange
            font_size='16sp'
        )
        pause_btn.bind(on_press=self._on_pause)
        controls.add_widget(pause_btn)
        
        skip_btn = Button(
            text='⏭ Skip',
            size_hint_x=0.5,
            background_color=(1, 0.2, 0.2, 1),  # Red
            font_size='16sp'
        )
        skip_btn.bind(on_press=self._on_skip)
        controls.add_widget(skip_btn)
        
        self.add_widget(controls)

        # Volume controls row
        volume_controls = BoxLayout(orientation='horizontal', size_hint_y=0.12, spacing=10, padding=5)
        
        vol_down = Button(
            text='🔉',
            size_hint_x=0.25,
            background_color=(0.2, 0.5, 1, 1),
            font_size='20sp'
        )
        vol_down.bind(on_press=self._on_volume_down)
        volume_controls.add_widget(vol_down)

        self.volume_label = Label(
            text='Volume: 50%',
            font_size='16sp',
            color=(1, 1, 1, 1),
            size_hint_x=0.5,
            halign='center',
            valign='middle'
        )
        self.volume_label.bind(size=self._update_label_text_size)
        volume_controls.add_widget(self.volume_label)

        vol_up = Button(
            text='🔊',
            size_hint_x=0.25,
            background_color=(0.2, 1, 0.2, 1),
            font_size='20sp'
        )
        vol_up.bind(on_press=self._on_volume_up)
        volume_controls.add_widget(vol_up)

        self.add_widget(volume_controls)

        # Up Next label
        up_next_label = Label(
            text="↓ Queue ↓",
            font_size='14sp',
            size_hint_y=0.08,
            color=(1, 0.84, 0.31, 1),  # Golden yellow
            bold=True
        )
        self.add_widget(up_next_label)

        # Queue list with better styling
        scroll_view = ScrollView(size_hint_y=0.43)
        self.queue_list = GridLayout(
            cols=1,
            spacing=3,
            size_hint_y=None,
            padding=8
        )
        self.queue_list.bind(minimum_height=self.queue_list.setter('height'))
        scroll_view.add_widget(self.queue_list)
        self.add_widget(scroll_view)


    # -------------------------
    # Thread-safe public API
    # -------------------------
    @mainthread
    def update_song(self, song_name: Optional[str]):
        """
        Public method called by controller. Uses @mainthread decorator
        to ensure it runs on the main GUI thread, even if called from another thread.
        """
        if not song_name:
            song_name = "<<< NO SONG PROVIDED >>>"
        self.current_song = song_name
        print("Called update_song with song_name:", song_name)
        self._on_update_song(self.current_song)

    @mainthread
    def update_queue(self, songs: List[str]):
        """Update queue display on main thread."""
        print("Called update_queue")
        self._on_update_queue(list(songs or []))

    def set_playing_state(self, is_playing: bool):
        """Optional method for UI state management."""
        pass

    def set_connected(self):
        """Show the connection status as connected."""
        if self.connection_status_label:
            self.connection_status_label.text = '● Connected'
            self.connection_status_label.color = (0.2, 0.95, 0.35, 1)

    def set_disconnected(self):
        """Show the connection status as disconnected."""
        if self.connection_status_label:
            self.connection_status_label.text = '● Disconnected'
            self.connection_status_label.color = (0.95, 0.2, 0.2, 1)

    # -------------------------
    # UI update methods (run on main thread)
    # -------------------------
    def _on_update_song(self, song_name: str):
        print("Called _on_update_song")
        log.info(f"_on_update_song called with: {song_name!r}")
        self.song_label.text = f"Now Playing:\n{song_name}"

    def _on_update_queue(self, songs: List[str]):
        log.info("_on_update_queue called, count=%d", len(songs))
        self.queue_list.clear_widgets()
        for i, s in enumerate(songs[:10], 1):
            queue_item = Label(
                text=f"{i}. {s}",
                font_size='15sp',
                size_hint_y=None,
                height=35,
                color=(0.9, 0.9, 0.9, 1),
                bold=False
            )
            self.queue_list.add_widget(queue_item)

    def _on_pause(self, instance):
        """Handle pause button press."""
        print("Pause button pressed")
        if self.ui_controller:
            self.ui_controller.handle_pause()

    def _on_skip(self, instance):
        """Handle skip button press."""
        print("Skip button pressed")
        if self.ui_controller:
            self.ui_controller.skip()

    def _on_volume_down(self, instance):
        """Handle volume down button press."""
        print("Volume down pressed")
        if self.ui_controller:
            self.ui_controller.volume_down()

    def _on_volume_up(self, instance):
        """Handle volume up button press."""
        print("Volume up pressed")
        if self.ui_controller:
            self.ui_controller.volume_up()

    def update_volume(self, volume: int):
        """Update the volume label from the audio controller."""
        if self.volume_label:
            self.volume_label.text = f"Volume: {volume}%"

    def _update_label_text_size(self, instance, value):
        instance.text_size = (value[0], None)

    def _update_cpu_temp(self, dt):
        temp = self._read_cpu_temp()
        if self.cpu_temp_label:
            self.cpu_temp_label.text = f"CPU: {temp}°C"

    def _read_cpu_temp(self):
        # Raspberry Pi usually exposes temperature here
        thermal_path = '/sys/class/thermal/thermal_zone0/temp'
        try:
            if os.path.exists(thermal_path):
                with open(thermal_path, 'r') as f:
                    raw = f.read().strip()
                if raw.isdigit():
                    return round(int(raw) / 1000, 1)
        except Exception:
            pass

        # Fallback to vcgencmd if available
        try:
            from subprocess import check_output
            output = check_output(['vcgencmd', 'measure_temp'], text=True).strip()
            if output.startswith('temp='):
                return float(output.split('=')[1].replace("'C", ""))
        except Exception:
            pass

        return '--'

    # -------------------------
    # Input: keyboard quit
    # -------------------------
    def on_keyboard(self, window, key, scancode, codepoint, modifier):
        if codepoint in ('q', 'escape'):
            App.get_running_app().stop()
            return True
        return False

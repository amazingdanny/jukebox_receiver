

import logging
from typing import List, Optional
import os

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.widget import Widget
from kivy.uix.scrollview import ScrollView
from kivy.config import Config
from kivy.core.window import Window
from kivy.core.text import LabelBase
from kivy.clock import Clock, mainthread
from kivy.graphics import Color, Rectangle, RoundedRectangle, Ellipse, Triangle, Quad
from kivy.graphics.texture import Texture
from kivy.properties import NumericProperty

#Window.fullscreen = 'fake'
#Window.size = (1920, 1080)
def show_size(dt):
    print("Window size:", Window.size)
    print("Window system size:", Window.system_size)

Clock.schedule_once(show_size, 2)

log = logging.getLogger("kivy_ui")
logging.basicConfig(level=logging.INFO)


# ============================================================
# Palette (red theme)
# ============================================================
BG_COLOR = (0.09, 0.03, 0.03, 1)
GLOW_RED_1 = (0.85, 0.15, 0.15)
GLOW_RED_2 = (0.95, 0.35, 0.15)

CARD_COLOR = (1, 1, 1, 0.045)
TITLE_COLOR = (1, 0.4, 0.35, 1)
SUBTLE_TEXT = (0.72, 0.58, 0.58, 1)

CONNECTED_COLOR = (0.2, 0.9, 0.4, 1)
DISCONNECTED_COLOR = (0.95, 0.25, 0.25, 1)

NOW_PLAYING_LABEL_COLOR = (1, 0.5, 0.4, 1)
SONG_TITLE_COLOR = (0.98, 0.96, 0.96, 1)

ALBUM_ART_C1 = (220, 40, 40)
ALBUM_ART_C2 = (255, 120, 40)

PAUSE_BTN_C1 = (205, 30, 30)
PAUSE_BTN_C2 = (255, 95, 40)

SKIP_BTN_C1 = (150, 20, 45)
SKIP_BTN_C2 = (220, 45, 80)

SLIDER_TRACK_COLOR = (1, 1, 1, 0.08)
SLIDER_FILL_C1 = (215, 35, 35)
SLIDER_FILL_C2 = (255, 130, 60)

VOL_DOWN_COLOR = (0.6, 0.18, 0.18, 1)
VOL_UP_COLOR = (0.85, 0.3, 0.15, 1)

BADGE_COLORS = [
    (0.95, 0.35, 0.25, 1),
    (0.8, 0.15, 0.25, 1),
    (0.95, 0.55, 0.2, 1),
]


def _mix(c1, c2, t=0.5):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def make_diagonal_gradient_texture(c1, c2):
    """2x2 texture whose bilinear interpolation reads as a soft diagonal gradient."""
    mid = _mix(c1, c2)
    tex = Texture.create(size=(2, 2), colorfmt='rgb')
    buf = bytes(c1) + bytes(mid) + bytes(mid) + bytes(c2)
    tex.blit_buffer(buf, colorfmt='rgb', bufferfmt='ubyte')
    tex.mag_filter = 'linear'
    tex.min_filter = 'linear'
    return tex


def add_rounded_bg(widget, color=(1, 1, 1, 1), texture=None, radius=16):
    """Draws a rounded-rect background behind `widget` that tracks its pos/size.
    Returns (color_instruction, rect_instruction) so callers can restyle later."""
    with widget.canvas.before:
        color_instr = Color(*color)
        rect_instr = RoundedRectangle(pos=widget.pos, size=widget.size, radius=[radius], texture=texture)

    def _update(instance, _value):
        rect_instr.pos = instance.pos
        rect_instr.size = instance.size

    widget.bind(pos=_update, size=_update)
    return color_instr, rect_instr


class VectorIcon(Widget):
    """Draws simple hand-built icons (pause, skip, speaker, note, list, dot) using plain
    canvas shapes instead of unicode glyphs, so nothing depends on the system font having
    those characters (which is what caused the tofu/"missing glyph" boxes)."""

    def __init__(self, kind, color=(1, 1, 1, 1), **kwargs):
        super().__init__(**kwargs)
        self.kind = kind
        self._icon_color = color
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def set_color(self, color):
        self._icon_color = color
        self._redraw()

    def _redraw(self, *args):
        self.canvas.clear()
        s = min(self.width, self.height)
        if s <= 0:
            return
        ox = self.center_x - s / 2
        oy = self.center_y - s / 2
        cx, cy = self.center_x, self.center_y
        k = self.kind

        with self.canvas:
            Color(*self._icon_color)

            if k == 'pause':
                bar_w = s * 0.22
                gap = s * 0.16
                Rectangle(pos=(cx - gap / 2 - bar_w, oy + s * 0.15), size=(bar_w, s * 0.7))
                Rectangle(pos=(cx + gap / 2, oy + s * 0.15), size=(bar_w, s * 0.7))

            elif k == 'skip':
                tri_w = s * 0.42
                Triangle(points=[ox, oy + s * 0.15, ox, oy + s * 0.85, ox + tri_w, oy + s * 0.5])
                Rectangle(pos=(ox + tri_w + s * 0.1, oy + s * 0.15), size=(s * 0.16, s * 0.7))

            elif k in ('vol_down', 'vol_up'):
                body_w = s * 0.26
                body_h = s * 0.32
                Rectangle(pos=(ox, cy - body_h / 2), size=(body_w, body_h))
                Quad(points=[
                    ox + body_w, cy - body_h / 2,
                    ox + body_w, cy + body_h / 2,
                    ox + body_w + s * 0.26, cy + s * 0.38,
                    ox + body_w + s * 0.26, cy - s * 0.38,
                ])
                sign_x = ox + s * 0.74
                Rectangle(pos=(sign_x, cy - s * 0.05), size=(s * 0.2, s * 0.1))
                if k == 'vol_up':
                    Rectangle(pos=(sign_x + s * 0.05, cy - s * 0.15), size=(s * 0.1, s * 0.3))

            elif k == 'note':
                head_w = s * 0.42
                head_h = s * 0.3
                stem_w = s * 0.09
                Ellipse(pos=(ox, oy), size=(head_w, head_h))
                stem_x = ox + head_w - stem_w * 0.5
                Rectangle(pos=(stem_x, oy + head_h * 0.4), size=(stem_w, s * 0.62))
                Triangle(points=[
                    stem_x, oy + head_h * 0.4 + s * 0.62,
                    stem_x, oy + head_h * 0.4 + s * 0.4,
                    stem_x + s * 0.24, oy + head_h * 0.4 + s * 0.52,
                ])

            elif k == 'list':
                bar_h = max(2, s * 0.12)
                Rectangle(pos=(ox, oy + s * 0.76), size=(s, bar_h))
                Rectangle(pos=(ox, oy + s * 0.44), size=(s * 0.8, bar_h))
                Rectangle(pos=(ox, oy + s * 0.12), size=(s * 0.6, bar_h))

            elif k == 'dot':
                Ellipse(pos=(ox, oy), size=(s, s))


class IconTextButton(ButtonBehavior, BoxLayout):
    """A button with a vector icon on the left and a text label, painted with a
    diagonal gradient background instead of the default theme."""

    def __init__(self, c1, c2, icon_kind, label_text, radius=18, icon_size=34, font_size=18, **kwargs):
        super().__init__(orientation='horizontal', spacing=12, padding=(24, 0), **kwargs)
        tex = make_diagonal_gradient_texture(c1, c2)
        self._color_instr, self._rect_instr = add_rounded_bg(self, color=(1, 1, 1, 1), texture=tex, radius=radius)

        self.icon = VectorIcon(icon_kind, color=(1, 1, 1, 1), size_hint=(None, 1), width=icon_size)
        self.add_widget(self.icon)

        self.label = Label(
            text=label_text,
            font_size=font_size,
            bold=True,
            color=(1, 1, 1, 1),
            halign='left',
            valign='middle',
        )
        self.label.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
        self.add_widget(self.label)

    def on_press(self):
        self._color_instr.rgba = (0.85, 0.85, 0.85, 1)

    def on_release(self):
        self._color_instr.rgba = (1, 1, 1, 1)


class CircleIconButton(ButtonBehavior, BoxLayout):
    """A small round flat-color button showing a single centered vector icon."""

    def __init__(self, color, icon_kind, **kwargs):
        super().__init__(padding=10, **kwargs)
        self._base_color = color
        self._color_instr, self._rect_instr = add_rounded_bg(self, color=color, radius=100)
        self.icon = VectorIcon(icon_kind, color=(1, 1, 1, 1), size_hint=(1, 1))
        self.add_widget(self.icon)

    def on_size(self, *args):
        if hasattr(self, '_rect_instr'):
            self._rect_instr.radius = [min(self.width, self.height) / 2]

    def on_press(self):
        r, g, b, a = self._base_color
        self._color_instr.rgba = (r * 0.8, g * 0.8, b * 0.8, a)

    def on_release(self):
        self._color_instr.rgba = self._base_color


class VolumeSlider(Widget):
    """Touch-draggable volume slider styled like a gradient-filled rounded track."""

    value = NumericProperty(20)

    def __init__(self, on_drag=None, **kwargs):
        super().__init__(**kwargs)
        self.on_drag = on_drag  # callback(value) fired only from user touch
        self._track_h = 14
        self._thumb_r = 14

        with self.canvas:
            self._track_color = Color(*SLIDER_TRACK_COLOR)
            self._track_rect = RoundedRectangle(radius=[self._track_h / 2])

            fill_tex = make_diagonal_gradient_texture(SLIDER_FILL_C1, SLIDER_FILL_C2)
            self._fill_color = Color(1, 1, 1, 1)
            self._fill_rect = RoundedRectangle(radius=[self._track_h / 2], texture=fill_tex)

            self._thumb_color = Color(1, 1, 1, 1)
            self._thumb_ellipse = Ellipse()

        self.bind(pos=self._redraw, size=self._redraw, value=self._redraw)

    def _track_bounds(self):
        pad = self._thumb_r
        x0 = self.x + pad
        x1 = self.right - pad
        return x0, x1

    def _redraw(self, *args):
        y = self.center_y - self._track_h / 2
        self._track_rect.pos = (self.x, y)
        self._track_rect.size = (self.width, self._track_h)

        x0, x1 = self._track_bounds()
        frac = max(0.0, min(1.0, self.value / 100.0))
        fill_width = max(self._track_h, (x1 - x0) * frac + self._thumb_r)
        self._fill_rect.pos = (self.x, y)
        self._fill_rect.size = (fill_width, self._track_h)

        thumb_x = x0 + (x1 - x0) * frac
        self._thumb_ellipse.pos = (thumb_x - self._thumb_r, self.center_y - self._thumb_r)
        self._thumb_ellipse.size = (self._thumb_r * 2, self._thumb_r * 2)

    def _value_from_x(self, x):
        x0, x1 = self._track_bounds()
        if x1 <= x0:
            return self.value
        frac = (x - x0) / (x1 - x0)
        return max(0, min(100, round(frac * 100)))

    def set_value_silent(self, value):
        """Update the visual position without firing the drag callback (for external sync)."""
        self.value = max(0, min(100, value))

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            touch.grab(self)
            self.value = self._value_from_x(touch.x)
            if self.on_drag:
                self.on_drag(self.value)
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current is self:
            self.value = self._value_from_x(touch.x)
            if self.on_drag:
                self.on_drag(self.value)
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            return True
        return super().on_touch_up(touch)


class Waveform(Widget):
    """Decorative static equalizer-style bars under the song title."""

    HEIGHTS = [4, 10, 6, 14, 8, 4, 12, 6, 16, 8, 4, 10, 6, 14, 8, 4, 12, 6, 10, 4, 8, 6, 12, 4]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas:
            self._color = Color(0.95, 0.45, 0.35, 0.4)
            self._rects = [Rectangle() for _ in self.HEIGHTS]
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *args):
        n = len(self.HEIGHTS)
        if n == 0 or self.width <= 0:
            return
        gap = self.width / n
        bar_w = max(2, gap * 0.4)
        max_h = max(self.HEIGHTS)
        for i, h in enumerate(self.HEIGHTS):
            rect = self._rects[i]
            scaled_h = (h / max_h) * self.height
            rect.size = (bar_w, scaled_h)
            rect.pos = (self.x + gap * i + (gap - bar_w) / 2, self.center_y - scaled_h / 2)


class MusicPlayerUI(BoxLayout):
    QUEUE_ROWS_PER_COLUMN = 6

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = 18
        self.spacing = 14

        self.current_song = "No song playing"
        self.ui_controller = None
        self.is_paused = False
        self.cpu_temp_label = None
        self.connection_status_label = None
        self.connection_dot = None
        self.connection_pill_color = None
        self.volume_slider = None

        # Dark background with soft red corner glows.
        with self.canvas.before:
            Color(*BG_COLOR)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)

            Color(*GLOW_RED_1, 0.16)
            self._glow_1_outer = Ellipse()
            Color(*GLOW_RED_1, 0.22)
            self._glow_1_inner = Ellipse()

            Color(*GLOW_RED_2, 0.14)
            self._glow_2_outer = Ellipse()
            Color(*GLOW_RED_2, 0.20)
            self._glow_2_inner = Ellipse()

        self.bind(pos=self._update_bg, size=self._update_bg)
        self._update_bg(self, self.size)

        self._build_ui()
        self.update_song(self.current_song)
        Clock.schedule_interval(self._update_cpu_temp, 1)
        self._update_cpu_temp(0)

    def _update_bg(self, instance, value):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

        w, h = self.size
        outer = w * 0.55
        inner = w * 0.32

        self._glow_1_outer.size = (outer, outer)
        self._glow_1_outer.pos = (self.x - outer * 0.35, self.top - outer * 0.65)
        self._glow_1_inner.size = (inner, inner)
        self._glow_1_inner.pos = (self.x - inner * 0.35, self.top - inner * 0.65)

        self._glow_2_outer.size = (outer, outer)
        self._glow_2_outer.pos = (self.right - outer * 0.65, self.top - outer * 0.65)
        self._glow_2_inner.size = (inner, inner)
        self._glow_2_inner.pos = (self.right - inner * 0.65, self.top - inner * 0.65)

    # -------------------------
    # Layout
    # -------------------------
    def _build_ui(self):
        # ---- Header row: title + CPU pill + connection pill ----
        header = BoxLayout(orientation='horizontal', size_hint_y=0.1, spacing=12)

        title_box = BoxLayout(orientation='horizontal', size_hint_x=0.5, spacing=8)
        title_icon = VectorIcon('note', color=TITLE_COLOR, size_hint=(None, 1), width=Window.width * 0.03)
        title_box.add_widget(title_icon)
        title = Label(
            text="Music Player",
            font_size=Window.width * 0.026,
            color=TITLE_COLOR,
            bold=True,
            halign='left',
            valign='middle',
        )
        title.bind(size=self._update_label_text_size)
        title_box.add_widget(title)
        header.add_widget(title_box)

        cpu_pill = BoxLayout(size_hint_x=0.28, padding=(14, 6))
        add_rounded_bg(cpu_pill, color=(1, 1, 1, 0.06), radius=100)
        self.cpu_temp_label = Label(
            text="CPU --°C",
            font_size=Window.width * 0.014,
            color=(1, 1, 1, 1),
            halign='center',
            valign='middle',
        )
        self.cpu_temp_label.bind(size=self._update_label_text_size)
        cpu_pill.add_widget(self.cpu_temp_label)
        header.add_widget(cpu_pill)

        conn_pill = BoxLayout(orientation='horizontal', size_hint_x=0.28, padding=(14, 6), spacing=8)
        self.connection_pill_color, _ = add_rounded_bg(conn_pill, color=(*DISCONNECTED_COLOR[:3], 0.15), radius=100)
        self.connection_dot = VectorIcon('dot', color=DISCONNECTED_COLOR, size_hint=(None, 1), width=14)
        conn_pill.add_widget(self.connection_dot)
        self.connection_status_label = Label(
            text='Disconnected',
            font_size=Window.width * 0.014,
            color=DISCONNECTED_COLOR,
            halign='left',
            valign='middle',
            bold=True,
        )
        self.connection_status_label.bind(size=self._update_label_text_size)
        conn_pill.add_widget(self.connection_status_label)
        header.add_widget(conn_pill)

        self.add_widget(header)

        # ---- Now playing card ----
        now_playing_card = BoxLayout(orientation='horizontal', size_hint_y=0.3, padding=20, spacing=18)
        add_rounded_bg(now_playing_card, color=CARD_COLOR, radius=24)

        album_art = BoxLayout(size_hint_x=0.3)
        art_tex = make_diagonal_gradient_texture(ALBUM_ART_C1, ALBUM_ART_C2)
        add_rounded_bg(album_art, color=(1, 1, 1, 1), texture=art_tex, radius=20)
        note_icon = VectorIcon('note', color=(1, 1, 1, 0.9), size_hint=(1, 1))
        album_art.add_widget(note_icon)
        now_playing_card.add_widget(album_art)

        song_info = BoxLayout(orientation='vertical', size_hint_x=0.7, spacing=6)
        now_playing_tag = Label(
            text="NOW PLAYING",
            font_size=Window.width * 0.013,
            color=NOW_PLAYING_LABEL_COLOR,
            bold=True,
            size_hint_y=0.25,
            halign='left',
            valign='bottom',
        )
        now_playing_tag.bind(size=self._update_label_text_size)
        song_info.add_widget(now_playing_tag)

        self.song_label = Label(
            text=self.current_song,
            font_size=Window.width * 0.028,
            size_hint_y=0.45,
            color=SONG_TITLE_COLOR,
            bold=True,
            halign='left',
            valign='middle',
        )
        self.song_label.bind(size=self._update_label_text_size)
        song_info.add_widget(self.song_label)

        song_info.add_widget(Waveform(size_hint_y=0.3))

        now_playing_card.add_widget(song_info)
        self.add_widget(now_playing_card)

        # ---- Control buttons ----
        controls = BoxLayout(orientation='horizontal', size_hint_y=0.13, spacing=14)

        pause_btn = IconTextButton(
            PAUSE_BTN_C1, PAUSE_BTN_C2, 'pause', 'Pause / Resume',
            icon_size=Window.width * 0.026,
            font_size=Window.width * 0.018,
        )
        pause_btn.bind(on_release=self._on_pause)
        controls.add_widget(pause_btn)

        skip_btn = IconTextButton(
            SKIP_BTN_C1, SKIP_BTN_C2, 'skip', 'Skip',
            icon_size=Window.width * 0.026,
            font_size=Window.width * 0.018,
        )
        skip_btn.bind(on_release=self._on_skip)
        controls.add_widget(skip_btn)

        self.add_widget(controls)

        # ---- Volume card ----
        volume_card = BoxLayout(orientation='vertical', size_hint_y=0.17, padding=(20, 12), spacing=6)
        add_rounded_bg(volume_card, color=CARD_COLOR, radius=24)

        volume_title = Label(
            text="VOLUME",
            font_size=Window.width * 0.012,
            color=SUBTLE_TEXT,
            bold=True,
            size_hint_y=0.3,
            halign='left',
            valign='middle',
        )
        volume_title.bind(size=self._update_label_text_size)
        volume_card.add_widget(volume_title)

        volume_row = BoxLayout(orientation='horizontal', size_hint_y=0.7, spacing=14)

        vol_down = CircleIconButton(VOL_DOWN_COLOR, 'vol_down', size_hint_x=0.12)
        vol_down.bind(on_release=self._on_volume_down)
        volume_row.add_widget(vol_down)

        self.volume_slider = VolumeSlider(on_drag=self._on_slider_drag, size_hint_x=0.6)
        volume_row.add_widget(self.volume_slider)

        vol_up = CircleIconButton(VOL_UP_COLOR, 'vol_up', size_hint_x=0.12)
        vol_up.bind(on_release=self._on_volume_up)
        volume_row.add_widget(vol_up)

        volume_card.add_widget(volume_row)

        self.volume_label = Label(
            text='Volume: 20%',
            font_size=Window.width * 0.015,
            color=(1, 1, 1, 1),
            size_hint_y=0.3,
            halign='center',
            valign='middle',
        )
        self.volume_label.bind(size=self._update_label_text_size)
        volume_card.add_widget(self.volume_label)

        self.add_widget(volume_card)

        # ---- Up Next header ----
        up_next_header = BoxLayout(orientation='horizontal', size_hint_y=0.06, spacing=8)
        list_icon = VectorIcon('list', color=(0.95, 0.95, 1, 1), size_hint=(None, 1), width=Window.width * 0.022)
        up_next_header.add_widget(list_icon)
        up_next_label = Label(
            text="Up Next",
            font_size=Window.width * 0.018,
            color=(0.95, 0.95, 1, 1),
            bold=True,
            halign='left',
            valign='middle',
        )
        up_next_label.bind(size=self._update_label_text_size)
        up_next_header.add_widget(up_next_label)

        self.queue_count_label = Label(
            text="0 songs",
            font_size=Window.width * 0.014,
            color=SUBTLE_TEXT,
            halign='right',
            valign='middle',
        )
        self.queue_count_label.bind(size=self._update_label_text_size)
        up_next_header.add_widget(self.queue_count_label)

        self.add_widget(up_next_header)

        # ---- Queue: two columns, left fills first, overflow goes to the right ----
        queue_area = ScrollView(size_hint_y=0.4, do_scroll_x=False)
        queue_columns = BoxLayout(orientation='horizontal', spacing=16, size_hint_y=None)
        queue_columns.bind(minimum_height=queue_columns.setter('height'))

        self.queue_col_left = GridLayout(cols=1, spacing=8, size_hint_y=None, size_hint_x=0.5)
        self.queue_col_left.bind(minimum_height=self.queue_col_left.setter('height'))
        self.queue_col_right = GridLayout(cols=1, spacing=8, size_hint_y=None, size_hint_x=0.5)
        self.queue_col_right.bind(minimum_height=self.queue_col_right.setter('height'))

        queue_columns.add_widget(self.queue_col_left)
        queue_columns.add_widget(self.queue_col_right)
        queue_area.add_widget(queue_columns)
        self.add_widget(queue_area)

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

    @mainthread
    def set_connected(self):
        """Show the connection status as connected."""
        if self.connection_status_label:
            self.connection_status_label.text = 'Connected'
            self.connection_status_label.color = CONNECTED_COLOR
        if self.connection_dot:
            self.connection_dot.set_color(CONNECTED_COLOR)
        if self.connection_pill_color:
            self.connection_pill_color.rgba = (*CONNECTED_COLOR[:3], 0.15)

    @mainthread
    def set_disconnected(self):
        """Show the connection status as disconnected."""
        if self.connection_status_label:
            self.connection_status_label.text = 'Disconnected'
            self.connection_status_label.color = DISCONNECTED_COLOR
        if self.connection_dot:
            self.connection_dot.set_color(DISCONNECTED_COLOR)
        if self.connection_pill_color:
            self.connection_pill_color.rgba = (*DISCONNECTED_COLOR[:3], 0.15)

    # -------------------------
    # UI update methods (run on main thread)
    # -------------------------
    def _on_update_song(self, song_name: str):
        print("Called _on_update_song")
        log.info(f"_on_update_song called with: {song_name!r}")
        self.song_label.text = song_name

    def _build_queue_row(self, index, song_name):
        row = BoxLayout(orientation='horizontal', size_hint_y=None, height=46, padding=(12, 6), spacing=12)
        add_rounded_bg(row, color=(1, 1, 1, 0.04), radius=14)

        badge_color = BADGE_COLORS[(index - 1) % len(BADGE_COLORS)]
        badge = BoxLayout(size_hint_x=None, width=32)
        add_rounded_bg(badge, color=badge_color, radius=100)
        badge_label = Label(text=str(index), font_size=16, color=(1, 1, 1, 1), bold=True)
        badge.add_widget(badge_label)
        row.add_widget(badge)

        song_label = Label(
            text=song_name,
            font_size=Window.width * 0.016,
            color=(0.92, 0.92, 0.97, 1),
            halign='left',
            valign='middle',
        )
        song_label.bind(size=self._update_label_text_size)
        row.add_widget(song_label)

        return row

    def _on_update_queue(self, songs: List[str]):
        log.info("_on_update_queue called, count=%d", len(songs))
        self.queue_col_left.clear_widgets()
        self.queue_col_right.clear_widgets()
        self.queue_count_label.text = f"{len(songs)} song{'s' if len(songs) != 1 else ''}"

        per_column = self.QUEUE_ROWS_PER_COLUMN
        visible = songs[:per_column * 2]
        left_songs = visible[:per_column]
        right_songs = visible[per_column:]

        for i, s in enumerate(left_songs, 1):
            self.queue_col_left.add_widget(self._build_queue_row(i, s))
        for i, s in enumerate(right_songs, per_column + 1):
            self.queue_col_right.add_widget(self._build_queue_row(i, s))

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

    def _on_slider_drag(self, value):
        """Fired live while the user drags the volume slider."""
        if self.ui_controller:
            self.ui_controller.set_volume(value)

    @mainthread
    def update_volume(self, volume: int):
        """Update the volume label and slider position from the audio controller."""
        if self.volume_label:
            self.volume_label.text = f"Volume: {volume}%"
        if self.volume_slider:
            self.volume_slider.set_value_silent(volume)

    def _update_label_text_size(self, instance, value):
        instance.text_size = (value[0], None)

    def _update_cpu_temp(self, dt):
        temp = self._read_cpu_temp()
        if self.cpu_temp_label:
            self.cpu_temp_label.text = f"CPU {temp}°C"

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



import io
import logging
import math
from typing import List, Optional
import os

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.widget import Widget
from kivy.uix.image import Image as KivyImage
from kivy.uix.scrollview import ScrollView
from kivy.uix.anchorlayout import AnchorLayout
from kivy.config import Config
from kivy.core.window import Window
from kivy.core.text import LabelBase
from kivy.core.image import Image as CoreImage
from kivy.clock import Clock, mainthread
from kivy.graphics import Color, Rectangle, RoundedRectangle, Ellipse, Triangle, Quad, Line
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
# Palette (Retro Hardware theme — Paper White)
# ============================================================
BG_STRIPE_1 = (22, 21, 26)   # brushed-panel diagonal stripe, dark
BG_STRIPE_2 = (28, 27, 32)   # brushed-panel diagonal stripe, slightly lighter

PANEL_BORDER = (0.227, 0.220, 0.259, 1)     # chassis / bevel shadow edge
PANEL_BORDER_LIGHT = (0.337, 0.329, 0.384, 1)  # component border / bevel highlight
INSET_BG = (0.063, 0.063, 0.078, 1)         # dark inset panel fill
BUTTON_FILL = (0.149, 0.141, 0.173, 1)      # button/knob body fill
BUTTON_BEVEL_LIGHT = (0.416, 0.408, 0.471, 1)

ACCENT = (0.949, 0.929, 0.878, 1)           # muted cream-white "LCD" glow color
ACCENT_DIM = (0.659, 0.624, 0.541, 1)       # muted tan-grey for secondary labels
SONG_TEXT_MUTED = (0.72, 0.70, 0.64, 1)     # queue song filenames

CONNECTION_ON_COLOR = (1, 0.82, 0.15, 1)    # yellow lightning bolt when connected
CONNECTION_OFF_COLOR = (1, 1, 1, 1)         # white lightning bolt when not connected


def make_stripe_texture(c1, c2, tile=8):
    """Small tileable diagonal two-tone stripe texture for the brushed-panel background."""
    buf = bytearray()
    for y in range(tile):
        for x in range(tile):
            band = ((x + y) // 2) % 2
            color = c1 if band == 0 else c2
            buf.extend(color)
    tex = Texture.create(size=(tile, tile), colorfmt='rgb')
    tex.blit_buffer(bytes(buf), colorfmt='rgb', bufferfmt='ubyte')
    tex.wrap = 'repeat'
    tex.mag_filter = 'nearest'
    tex.min_filter = 'nearest'
    return tex


AUDIO_EXTENSIONS = ('.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac')


def strip_extension(name):
    """Drop a trailing audio file extension (.mp3, .wav, ...) for display, leaving
    prefixes like "Paused: " intact since the extension is always at the very end."""
    if not name:
        return name
    for ext in AUDIO_EXTENSIONS:
        if name.lower().endswith(ext):
            return name[:-len(ext)]
    return name


def add_flat_panel(widget, fill_color, border_color, border_width=1, radius=4):
    """Flat fill plus a plain rectangular border outline that tracks pos/size —
    the bordered-inset-box look used throughout the hardware theme."""
    with widget.canvas.before:
        fill_c = Color(*fill_color)
        fill_rect = RoundedRectangle(pos=widget.pos, size=widget.size, radius=[radius])
        border_c = Color(*border_color)
        border_line = Line(
            rounded_rectangle=(widget.x, widget.y, widget.width, widget.height, radius),
            width=border_width,
        )

    def _update(instance, _value):
        fill_rect.pos = instance.pos
        fill_rect.size = instance.size
        border_line.rounded_rectangle = (instance.x, instance.y, instance.width, instance.height, radius)

    widget.bind(pos=_update, size=_update)
    return fill_c, border_c


def add_bevel_button_bg(widget, fill_color, radius=3, border_width=2):
    """Flat fill with a beveled border: a dark outline on every edge, plus a bright
    highlight along the top and left edges to read as a raised physical button."""
    with widget.canvas.before:
        fill_c = Color(*fill_color)
        fill_rect = RoundedRectangle(pos=widget.pos, size=widget.size, radius=[radius])
        Color(*PANEL_BORDER)
        dark_line = Line(
            rounded_rectangle=(widget.x, widget.y, widget.width, widget.height, radius),
            width=border_width,
        )
        Color(*BUTTON_BEVEL_LIGHT)
        light_line_top = Line(width=border_width)
        light_line_left = Line(width=border_width)

    def _update(instance, _value):
        fill_rect.pos = instance.pos
        fill_rect.size = instance.size
        dark_line.rounded_rectangle = (instance.x, instance.y, instance.width, instance.height, radius)
        inset = border_width / 2
        light_line_top.points = [instance.x + radius, instance.top - inset, instance.right - radius, instance.top - inset]
        light_line_left.points = [instance.x + inset, instance.y + radius, instance.x + inset, instance.top - radius]

    widget.bind(pos=_update, size=_update)
    return fill_c


class VectorIcon(Widget):
    """Draws simple hand-built icons (pause, skip, note, vinyl, list, dot) using plain
    canvas shapes instead of unicode glyphs, so nothing depends on the system font having
    those characters (which is what caused the tofu/"missing glyph" boxes)."""

    def __init__(self, kind, color=(1, 1, 1, 1), color2=None, **kwargs):
        super().__init__(**kwargs)
        self.kind = kind
        self._icon_color = color
        self._icon_color2 = color2 if color2 is not None else color
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def set_color(self, color, color2=None):
        self._icon_color = color
        self._icon_color2 = color2 if color2 is not None else color
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

            elif k == 'vinyl':
                Line(circle=(cx, cy, s * 0.42), width=max(1.2, s * 0.018))
                Color(*self._icon_color2)
                Line(circle=(cx, cy, s * 0.32), width=max(1, s * 0.01))
                Line(circle=(cx, cy, s * 0.24), width=max(1, s * 0.01))
                Color(*self._icon_color)
                r_label = s * 0.16
                Ellipse(pos=(cx - r_label, cy - r_label), size=(r_label * 2, r_label * 2))
                r_hole = s * 0.045
                Color(*INSET_BG)
                Ellipse(pos=(cx - r_hole, cy - r_hole), size=(r_hole * 2, r_hole * 2))

            elif k == 'list':
                bar_h = max(2, s * 0.12)
                Rectangle(pos=(ox, oy + s * 0.76), size=(s, bar_h))
                Rectangle(pos=(ox, oy + s * 0.44), size=(s * 0.8, bar_h))
                Rectangle(pos=(ox, oy + s * 0.12), size=(s * 0.6, bar_h))

            elif k == 'clear':
                Rectangle(pos=(ox + s * 0.15, oy + s * 0.78), size=(s * 0.7, s * 0.08))
                Rectangle(pos=(ox + s * 0.38, oy + s * 0.85), size=(s * 0.24, s * 0.07))
                Quad(points=[
                    ox + s * 0.22, oy + s * 0.72,
                    ox + s * 0.78, oy + s * 0.72,
                    ox + s * 0.68, oy + s * 0.08,
                    ox + s * 0.32, oy + s * 0.08,
                ])

            elif k == 'dot':
                Ellipse(pos=(ox, oy), size=(s, s))

            elif k == 'lightning':
                def _pt(px, py):
                    return (ox + px * s, oy + py * s)

                Triangle(points=[*_pt(0.6, 1.0), *_pt(0.15, 0.45), *_pt(0.55, 0.45)])
                Triangle(points=[*_pt(0.45, 0.55), *_pt(0.85, 0.55), *_pt(0.4, 0.0)])


class IconTextButton(ButtonBehavior, AnchorLayout):
    """A bordered, beveled hardware-style button with a vector icon and a text label.

    The icon and label are sized to their own natural dimensions and centered as one
    fixed-size unit via explicit pos_hint math (not Label's `valign`, which does not
    reliably vertically center text against a sibling widget in a stretched row) —
    this guarantees the icon and text align on the same vertical center regardless of
    font metrics or row height.
    """

    def __init__(self, icon_kind, label_text, radius=3, icon_size=34, font_size=18, padding_x=24, **kwargs):
        super().__init__(padding=(padding_x, 0), **kwargs)
        self._fill_color = add_bevel_button_bg(self, BUTTON_FILL, radius=radius)

        content = BoxLayout(orientation='horizontal', spacing=10, size_hint=(None, None))

        self.icon = VectorIcon(
            icon_kind, color=ACCENT,
            size_hint=(None, None), size=(icon_size, icon_size),
            pos_hint={'center_y': 0.5},
        )
        content.add_widget(self.icon)

        self.label = Label(
            text=label_text.upper(),
            font_size=font_size,
            bold=True,
            color=ACCENT,
            size_hint=(None, None),
            pos_hint={'center_y': 0.5},
        )
        self.label.texture_update()
        self.label.size = self.label.texture_size
        self.label.bind(texture_size=lambda inst, val: setattr(inst, 'size', val))
        content.add_widget(self.label)

        def _sync_content_size(*_args):
            content.width = self.icon.width + content.spacing + self.label.width
            content.height = max(self.icon.height, self.label.height)

        self.icon.bind(size=_sync_content_size)
        self.label.bind(size=_sync_content_size)
        _sync_content_size()

        self.add_widget(content)

    def on_press(self):
        self._fill_color.rgba = PANEL_BORDER

    def on_release(self):
        self._fill_color.rgba = BUTTON_FILL


class CircleIconButton(ButtonBehavior, AnchorLayout):
    """A small beveled button showing a single centered vector icon — used for the
    volume up/down nudge buttons beside the knob."""

    def __init__(self, icon_kind, radius=4, **kwargs):
        super().__init__(padding=6, **kwargs)
        self._fill_color = add_bevel_button_bg(self, BUTTON_FILL, radius=radius)
        self.icon = VectorIcon(icon_kind, color=ACCENT, size_hint=(1, 1))
        self.add_widget(self.icon)

    def on_press(self):
        self._fill_color.rgba = PANEL_BORDER

    def on_release(self):
        self._fill_color.rgba = BUTTON_FILL


class VolumeKnob(Widget):
    """Touch-draggable rotary volume knob: drag up/down to sweep the pointer through a
    270-degree arc, like a physical hardware dial."""

    value = NumericProperty(20)

    def __init__(self, on_drag=None, **kwargs):
        super().__init__(**kwargs)
        self.on_drag = on_drag  # callback(value) fired only from user touch

        with self.canvas:
            Color(*BUTTON_FILL)
            self._body_ellipse = Ellipse()
            Color(*PANEL_BORDER_LIGHT)
            self._border_line = Line(width=2)
            Color(*ACCENT)
            self._pointer_line = Line(width=2)

        self.bind(pos=self._redraw, size=self._redraw, value=self._redraw)

    def _redraw(self, *args):
        s = min(self.width, self.height)
        if s <= 0:
            return
        r = s / 2 * 0.85
        cx, cy = self.center_x, self.center_y

        self._body_ellipse.pos = (cx - r, cy - r)
        self._body_ellipse.size = (r * 2, r * 2)
        self._border_line.circle = (cx, cy, r)

        angle_deg = 225 - (max(0, min(100, self.value)) / 100.0) * 270
        angle_rad = math.radians(angle_deg)
        inner, outer = r * 0.2, r * 0.85
        self._pointer_line.points = [
            cx + inner * math.cos(angle_rad), cy + inner * math.sin(angle_rad),
            cx + outer * math.cos(angle_rad), cy + outer * math.sin(angle_rad),
        ]

    def set_value_silent(self, value):
        """Update the visual position without firing the drag callback (for external sync)."""
        self.value = max(0, min(100, value))

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            touch.grab(self)
            touch.ud['knob_start_y'] = touch.y
            touch.ud['knob_start_val'] = self.value
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current is self:
            delta = touch.y - touch.ud['knob_start_y']
            self.value = max(0, min(100, touch.ud['knob_start_val'] + delta / 3.0))
            if self.on_drag:
                self.on_drag(self.value)
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            return True
        return super().on_touch_up(touch)


class VerticalVolumeSlider(Widget):
    """Touch-draggable vertical volume slider: a bordered inset track that fills from
    the bottom up, with a small thumb marker — a second, more precise way to set the
    volume alongside the knob."""

    value = NumericProperty(20)

    def __init__(self, on_drag=None, **kwargs):
        super().__init__(**kwargs)
        self.on_drag = on_drag  # callback(value) fired only from user touch
        self._track_w = 10
        self._thumb_h = 6

        with self.canvas:
            Color(*INSET_BG)
            self._track_rect = Rectangle()
            Color(*PANEL_BORDER_LIGHT)
            self._border_line = Line(width=1)
            Color(*ACCENT)
            self._fill_rect = Rectangle()
            self._thumb_rect = Rectangle()

        self.bind(pos=self._redraw, size=self._redraw, value=self._redraw)

    def _redraw(self, *args):
        x = self.center_x - self._track_w / 2
        self._track_rect.pos = (x, self.y)
        self._track_rect.size = (self._track_w, self.height)
        self._border_line.rectangle = (x, self.y, self._track_w, self.height)

        frac = max(0.0, min(1.0, self.value / 100.0))
        fill_h = max(2, self.height * frac)
        self._fill_rect.pos = (x, self.y)
        self._fill_rect.size = (self._track_w, fill_h)

        thumb_y = max(self.y, min(self.top - self._thumb_h, self.y + fill_h - self._thumb_h / 2))
        self._thumb_rect.pos = (x - 4, thumb_y)
        self._thumb_rect.size = (self._track_w + 8, self._thumb_h)

    def _value_from_y(self, y):
        if self.height <= 0:
            return self.value
        frac = (y - self.y) / self.height
        return max(0, min(100, round(frac * 100)))

    def set_value_silent(self, value):
        """Update the visual position without firing the drag callback (for external sync)."""
        self.value = max(0, min(100, value))

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            touch.grab(self)
            self.value = self._value_from_y(touch.y)
            if self.on_drag:
                self.on_drag(self.value)
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current is self:
            self.value = self._value_from_y(touch.y)
            if self.on_drag:
                self.on_drag(self.value)
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            return True
        return super().on_touch_up(touch)


class SongProgressBar(Widget):
    """Read-only playback-position bar: a bordered inset track with a flat amber fill
    that grows to match how far into the current song playback is."""

    value = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._track_h = 8

        with self.canvas:
            Color(*INSET_BG)
            self._track_rect = Rectangle()
            Color(*PANEL_BORDER_LIGHT)
            self._border_line = Line(width=1)
            Color(*ACCENT)
            self._fill_rect = Rectangle()

        self.bind(pos=self._redraw, size=self._redraw, value=self._redraw)

    def _redraw(self, *args):
        y = self.center_y - self._track_h / 2
        self._track_rect.pos = (self.x, y)
        self._track_rect.size = (self.width, self._track_h)
        self._border_line.rectangle = (self.x, y, self.width, self._track_h)

        frac = max(0.0, min(1.0, self.value / 100.0))
        fill_w = max(2, self.width * frac)
        self._fill_rect.pos = (self.x, y)
        self._fill_rect.size = (fill_w, self._track_h)

    def set_progress(self, value):
        """Update the fill position. `value` is a 0-100 percentage."""
        self.value = max(0, min(100, value))


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
        self.connection_icon = None
        self.volume_knob = None
        self.volume_vslider = None
        self.album_art_box = None
        self.progress_bar = None

        # Brushed-panel background: a tiled diagonal stripe texture inside a chassis border.
        stripe_tex = make_stripe_texture(BG_STRIPE_1, BG_STRIPE_2)
        with self.canvas.before:
            Color(1, 1, 1, 1)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size, texture=stripe_tex)
            Color(*PANEL_BORDER)
            self._chassis_border = Line(width=3)

        self.bind(pos=self._update_bg, size=self._update_bg)
        self._update_bg(self, self.size)

        self._build_ui()
        self.update_song(self.current_song)
        Clock.schedule_interval(self._update_cpu_temp, 1)
        self._update_cpu_temp(0)
        Clock.schedule_interval(self._update_progress, 0.5)

    def _update_bg(self, instance, value):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

        tile_screen_px = 24  # how large each stripe tile renders on screen
        reps_x = max(1, self.width / tile_screen_px)
        reps_y = max(1, self.height / tile_screen_px)
        self._bg_rect.tex_coords = (0, 0, reps_x, 0, reps_x, reps_y, 0, reps_y)

        self._chassis_border.rectangle = (self.x + 1.5, self.y + 1.5, self.width - 3, self.height - 3)

    # -------------------------
    # Layout
    # -------------------------
    def _build_ui(self):
        # ---- Header row: title + CPU pill + connection pill ----
        header = BoxLayout(orientation='horizontal', size_hint_y=0.1, spacing=12)

        title_box = BoxLayout(orientation='horizontal', size_hint_x=0.5, spacing=8)
        title_icon_size = Window.width * 0.03
        title_icon = VectorIcon(
            'note', color=ACCENT,
            size_hint=(None, None), size=(title_icon_size, title_icon_size),
            pos_hint={'center_y': 0.5},
        )
        title_box.add_widget(title_icon)
        title = Label(
            text="Danny's Jukebox",
            font_size=Window.width * 0.024,
            color=ACCENT,
            bold=True,
            size_hint=(None, None),
            pos_hint={'center_y': 0.5},
        )
        title.texture_update()
        title.size = title.texture_size
        title.bind(texture_size=lambda inst, val: setattr(inst, 'size', val))
        title_box.add_widget(title)
        header.add_widget(title_box)

        cpu_pill = BoxLayout(size_hint_x=0.28, padding=(14, 6))
        add_flat_panel(cpu_pill, INSET_BG, PANEL_BORDER_LIGHT, radius=4)
        self.cpu_temp_label = Label(
            text="CPU --°C",
            font_size=Window.width * 0.013,
            color=ACCENT_DIM,
            bold=True,
            halign='center',
            valign='middle',
        )
        self.cpu_temp_label.bind(size=self._update_label_text_size)
        cpu_pill.add_widget(self.cpu_temp_label)
        header.add_widget(cpu_pill)

        conn_pill = BoxLayout(size_hint_x=0.14, padding=(10, 6))
        add_flat_panel(conn_pill, INSET_BG, PANEL_BORDER_LIGHT, radius=4)
        self.connection_icon = VectorIcon('lightning', color=CONNECTION_OFF_COLOR, size_hint=(1, 1))
        conn_pill.add_widget(self.connection_icon)
        header.add_widget(conn_pill)

        self.add_widget(header)

        # ---- Now playing panel ----
        now_playing_card = BoxLayout(orientation='horizontal', size_hint_y=0.3, padding=20, spacing=18)
        add_flat_panel(now_playing_card, INSET_BG, PANEL_BORDER_LIGHT, radius=6)

        album_art = BoxLayout(size_hint_x=0.3, padding=4)
        add_flat_panel(album_art, BUTTON_FILL, PANEL_BORDER_LIGHT, radius=3)
        self.album_art_box = album_art
        vinyl_icon = VectorIcon('vinyl', color=ACCENT, color2=ACCENT_DIM, size_hint=(1, 1))
        album_art.add_widget(vinyl_icon)
        now_playing_card.add_widget(album_art)

        song_info = BoxLayout(orientation='vertical', size_hint_x=0.7, spacing=6)
        now_playing_row = BoxLayout(orientation='horizontal', size_hint_y=0.32, spacing=8)
        now_playing_tag = Label(
            text="NOW PLAYING",
            font_size=Window.width * 0.013,
            color=ACCENT_DIM,
            bold=True,
            size_hint_x=None,
            halign='left',
            valign='middle',
        )
        now_playing_tag.bind(texture_size=lambda inst, val: setattr(inst, 'width', val[0]))
        now_playing_tag.bind(size=self._update_label_text_size)
        now_playing_row.add_widget(now_playing_tag)

        self.artist_label = Label(
            text="",
            font_size=Window.width * 0.017,
            color=ACCENT_DIM,
            bold=True,
            halign='left',
            valign='middle',
        )
        self.artist_label.bind(size=self._update_label_text_size)
        now_playing_row.add_widget(self.artist_label)

        song_info.add_widget(now_playing_row)

        self.song_label = Label(
            text=self.current_song,
            font_size=Window.width * 0.026,
            size_hint_y=0.38,
            color=ACCENT,
            bold=True,
            halign='left',
            valign='middle',
        )
        self.song_label.bind(size=self._update_label_text_size)
        song_info.add_widget(self.song_label)

        self.progress_bar = SongProgressBar(size_hint_y=0.3)
        song_info.add_widget(self.progress_bar)

        now_playing_card.add_widget(song_info)
        self.add_widget(now_playing_card)

        # ---- Control buttons with the volume knob (bigger, for precision) in between ----
        controls = BoxLayout(orientation='horizontal', size_hint_y=0.3, spacing=14)

        pause_btn = IconTextButton(
            'pause', 'Pause / Resume',
            icon_size=Window.width * 0.02,
            font_size=Window.width * 0.014,
            padding_x=8,
            size_hint_x=0.22,
            size_hint_y=0.62,
            pos_hint={'top': 1},
        )
        pause_btn.bind(on_release=self._on_pause)
        controls.add_widget(pause_btn)

        knob_col = BoxLayout(orientation='vertical', size_hint_x=0.56, spacing=4)

        # Vol buttons, knob, and slider are all sized directly off the knob's own
        # height and packed into a fixed-size row, then centered with an AnchorLayout.
        # (A plain stretchy BoxLayout left each widget's box far bigger than what it
        # actually draws — e.g. the knob's circle is capped to min(width, height), so a
        # box wider than it is tall left dead space between the knob and its neighbors
        # no matter how tight `spacing` was.)
        knob_row_wrap = AnchorLayout(size_hint_y=0.87)
        knob_row = BoxLayout(orientation='horizontal', size_hint=(None, None))
        knob_row_wrap.add_widget(knob_row)

        vol_buttons_col = BoxLayout(orientation='vertical', spacing=6, size_hint=(None, None))
        vol_up_btn = CircleIconButton('vol_up', size_hint=(1, 0.48))
        vol_up_btn.bind(on_release=self._on_volume_up)
        vol_buttons_col.add_widget(vol_up_btn)
        vol_down_btn = CircleIconButton('vol_down', size_hint=(1, 0.48))
        vol_down_btn.bind(on_release=self._on_volume_down)
        vol_buttons_col.add_widget(vol_down_btn)
        knob_row.add_widget(vol_buttons_col)

        self.volume_knob = VolumeKnob(on_drag=self._on_volume_drag, size_hint=(None, None))
        knob_row.add_widget(self.volume_knob)

        self.volume_vslider = VerticalVolumeSlider(on_drag=self._on_volume_drag, size_hint=(None, None))
        knob_row.add_widget(self.volume_vslider)

        def _size_knob_row(*_args):
            knob_h = knob_row_wrap.height
            if knob_h <= 0:
                return
            self.volume_knob.size = (knob_h, knob_h)
            vol_buttons_col.size = (knob_h * 0.42, knob_h)
            self.volume_vslider.size = (knob_h * 0.32, knob_h)
            # Gap is a fraction of the knob's own height, not a fixed pixel count, so it
            # scales the same way on any screen size.
            knob_row.spacing = knob_h * 0.9
            knob_row.size = (
                vol_buttons_col.width + self.volume_knob.width + self.volume_vslider.width
                + knob_row.spacing * 2,
                knob_h,
            )

        knob_row_wrap.bind(size=_size_knob_row)
        knob_col.add_widget(knob_row_wrap)
        self.volume_label = Label(
            text='20%',
            font_size=Window.width * 0.02,
            color=ACCENT,
            bold=True,
            size_hint_y=0.13,
            halign='center',
            valign='middle',
        )
        self.volume_label.bind(size=self._update_label_text_size)
        knob_col.add_widget(self.volume_label)
        controls.add_widget(knob_col)

        skip_btn = IconTextButton(
            'skip', 'Skip',
            icon_size=Window.width * 0.02,
            font_size=Window.width * 0.014,
            padding_x=8,
            size_hint_x=0.22,
            size_hint_y=0.62,
            pos_hint={'top': 1},
        )
        skip_btn.bind(on_release=self._on_skip)
        controls.add_widget(skip_btn)

        self.add_widget(controls)

        # ---- Up Next header ----
        up_next_header = BoxLayout(orientation='horizontal', size_hint_y=0.06, spacing=8)
        list_icon_size = Window.width * 0.02
        list_icon = VectorIcon(
            'list', color=ACCENT,
            size_hint=(None, None), size=(list_icon_size, list_icon_size),
            pos_hint={'center_y': 0.5},
        )
        up_next_header.add_widget(list_icon)
        up_next_label = Label(
            text="UP NEXT",
            font_size=Window.width * 0.017,
            color=ACCENT,
            bold=True,
            size_hint=(None, None),
            pos_hint={'center_y': 0.5},
        )
        up_next_label.texture_update()
        up_next_label.size = up_next_label.texture_size
        up_next_label.bind(texture_size=lambda inst, val: setattr(inst, 'size', val))
        up_next_header.add_widget(up_next_label)

        self.queue_count_label = Label(
            text="0 SONGS",
            font_size=Window.width * 0.013,
            color=ACCENT_DIM,
            bold=True,
            halign='right',
            valign='middle',
        )
        self.queue_count_label.bind(size=self._update_label_text_size)
        up_next_header.add_widget(self.queue_count_label)

        self.add_widget(up_next_header)

        # ---- Queue: three equal-width columns, sized to always fit on screen — row
        # height is computed from the actual available area (not a fixed pixel guess),
        # so QUEUE_ROWS_PER_COLUMN rows always fit with no scrolling and nothing ever
        # hangs off below the visible area.
        queue_area = BoxLayout(orientation='horizontal', spacing=16, size_hint_y=0.34)
        self.queue_columns = []
        self._last_queue = []
        self._queue_row_height = 32  # placeholder until the first real layout pass

        def _update_queue_row_height(*_args):
            spacing = 4
            rows = self.QUEUE_ROWS_PER_COLUMN
            available = queue_area.height - spacing * (rows - 1)
            self._queue_row_height = max(1, available / rows)
            self._on_update_queue(self._last_queue)

        for _ in range(3):
            col = BoxLayout(orientation='vertical', spacing=4, size_hint_x=1 / 3)
            queue_area.add_widget(col)
            self.queue_columns.append(col)

        queue_area.bind(height=_update_queue_row_height)
        self.add_widget(queue_area)

        # ---- Clear queue button, bottom right ----
        clear_row = BoxLayout(orientation='horizontal', size_hint_y=0.06)
        clear_row.add_widget(Widget())
        clear_btn = IconTextButton(
            'clear', 'Clear Queue',
            icon_size=Window.width * 0.018,
            font_size=Window.width * 0.013,
            padding_x=14,
            size_hint_x=0.28,
        )
        clear_btn.bind(on_release=self._on_clear_queue)
        clear_row.add_widget(clear_btn)
        self.add_widget(clear_row)

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
    def update_queue(self, songs: List):
        """Update queue display on main thread. `songs` is a list of (name, artist)
        tuples (artist may be None), as returned by AudioController.get_current_queue()."""
        print("Called update_queue")
        self._on_update_queue(list(songs or []))

    @mainthread
    def update_album_art(self, art):
        """Show the song's embedded cover art if available, otherwise fall back to the
        vinyl record icon. `art` is (image_bytes, mime_type) as returned by
        audiocontroller.get_album_art(), or None."""
        if not self.album_art_box:
            return
        self.album_art_box.clear_widgets()
        if art:
            image_bytes, mime = art
            ext = 'png' if mime and 'png' in mime else 'jpg'
            try:
                core_image = CoreImage(io.BytesIO(image_bytes), ext=ext)
                cover = KivyImage(texture=core_image.texture, allow_stretch=True, keep_ratio=True)
                self.album_art_box.add_widget(cover)
                return
            except Exception:
                log.warning("Failed to decode embedded album art", exc_info=True)
        self.album_art_box.add_widget(VectorIcon('vinyl', color=ACCENT, color2=ACCENT_DIM, size_hint=(1, 1)))

    @mainthread
    def update_artist(self, artist: Optional[str]):
        """Show the song's artist tag next to the NOW PLAYING label, if known."""
        if self.artist_label:
            self.artist_label.text = f"- {artist}" if artist else ""

    def set_playing_state(self, is_playing: bool):
        """Optional method for UI state management."""
        pass

    @mainthread
    def set_connected(self):
        """Show the connection status as connected: lightning bolt turns yellow."""
        if self.connection_icon:
            self.connection_icon.set_color(CONNECTION_ON_COLOR)

    @mainthread
    def set_disconnected(self):
        """Show the connection status as disconnected: lightning bolt turns white."""
        if self.connection_icon:
            self.connection_icon.set_color(CONNECTION_OFF_COLOR)

    # -------------------------
    # UI update methods (run on main thread)
    # -------------------------
    def _on_update_song(self, song_name: str):
        print("Called _on_update_song")
        log.info(f"_on_update_song called with: {song_name!r}")
        self.song_label.text = song_name

    def _build_queue_row(self, index, song_name, artist=None):
        # Single-line entry — title and artist sit side by side instead of stacked, so
        # each row only needs self._queue_row_height (an even share of the queue area).
        # That's what keeps QUEUE_ROWS_PER_COLUMN rows fitting on screen with no
        # scrolling and nothing hanging off below.
        row_height = self._queue_row_height

        pill = BoxLayout(
            orientation='horizontal', size_hint=(1, None), height=row_height,
            padding=(8, 2), spacing=8,
        )
        add_flat_panel(pill, INSET_BG, PANEL_BORDER_LIGHT, radius=4)

        badge = BoxLayout(size_hint_x=None, width=22)
        add_flat_panel(badge, INSET_BG, ACCENT, border_width=1, radius=2)
        badge_label = Label(text=str(index), font_size=11, color=ACCENT, bold=True)
        badge.add_widget(badge_label)
        pill.add_widget(badge)

        song_label = Label(
            text=song_name,
            font_size=Window.width * 0.013,
            color=ACCENT,
            bold=True,
            halign='left',
            valign='middle',
            shorten=True,
            shorten_from='right',
            size_hint=(0.6 if artist else 1, 1),
        )
        song_label.bind(size=self._update_label_text_size)
        pill.add_widget(song_label)

        if artist:
            artist_label = Label(
                text=artist,
                font_size=Window.width * 0.011,
                color=SONG_TEXT_MUTED,
                halign='left',
                valign='middle',
                shorten=True,
                shorten_from='right',
                size_hint=(0.4, 1),
            )
            artist_label.bind(size=self._update_label_text_size)
            pill.add_widget(artist_label)

        return pill

    def _on_update_queue(self, songs):
        log.info("_on_update_queue called, count=%d", len(songs))
        self._last_queue = songs
        for col in self.queue_columns:
            col.clear_widgets()
        self.queue_count_label.text = f"{len(songs)} SONG{'S' if len(songs) != 1 else ''}"

        # Each entry is (name, artist) from AudioController.get_current_queue(); plain
        # strings (name only) are still accepted so this keeps working if that ever
        # changes back.
        num_columns = len(self.queue_columns) or 1
        per_column = self.QUEUE_ROWS_PER_COLUMN
        visible = songs[:per_column * num_columns]

        def _row(i, entry):
            if isinstance(entry, (tuple, list)):
                name, artist = entry[0], entry[1] if len(entry) > 1 else None
            else:
                name, artist = entry, None
            return self._build_queue_row(i, strip_extension(name), artist)

        for col_index, col in enumerate(self.queue_columns):
            start = col_index * per_column
            column_songs = visible[start:start + per_column]
            for i, s in enumerate(column_songs, start + 1):
                col.add_widget(_row(i, s))

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

    def _on_clear_queue(self, instance):
        """Handle clear-queue button press."""
        print("Clear queue button pressed")
        if self.ui_controller:
            self.ui_controller.clear_queue()
            # clear_queue() doesn't push a UI refresh on its own (that normally happens
            # on the next song change), so update the on-screen list immediately here.
            self.update_queue([])

    def _on_volume_drag(self, value):
        """Fired live while the user drags the volume knob or slider."""
        if self.ui_controller:
            self.ui_controller.set_volume(value)

    def _on_volume_up(self, instance):
        """Handle volume up nudge button press."""
        if self.ui_controller:
            self.ui_controller.volume_up()

    def _on_volume_down(self, instance):
        """Handle volume down nudge button press."""
        if self.ui_controller:
            self.ui_controller.volume_down()

    @mainthread
    def update_volume(self, volume: int):
        """Update the volume readout, knob, and slider from the audio controller."""
        if self.volume_label:
            self.volume_label.text = f"{int(volume)}%"
        if self.volume_knob:
            self.volume_knob.set_value_silent(volume)
        if self.volume_vslider:
            self.volume_vslider.set_value_silent(volume)

    def _update_label_text_size(self, instance, value):
        instance.text_size = value

    def _update_progress(self, dt):
        if not self.ui_controller or not self.progress_bar:
            return
        getter = getattr(self.ui_controller, 'get_progress', None)
        if not getter:
            return
        current_ms, total_ms = getter()
        frac = (current_ms / total_ms * 100) if total_ms > 0 else 0
        self.progress_bar.set_progress(frac)

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

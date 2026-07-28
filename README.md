# Jukebox Receiver - Kivy Edition

A Raspberry Pi music player with network receiver capabilities using Kivy for the GUI.

sudo startx
sudo XAUTHORITY=/root/.Xauthority DISPLAY=:1 python main.py

## Installation

### Prerequisites
- Python 3.7+
- Raspberry Pi with audio output configured

### Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **For Raspberry Pi Framebuffer (optional):**
   If you're running on Raspberry Pi without X11, you may want to use the framebuffer:
   ```bash
   export KIVY_WINDOW=pygame
   export SDL_VIDEODRIVER=fbcon
   export SDL_FBDEV=/dev/fb0
   ```

3. **Configure music folder:**
   Edit `main.py` and set `MUSIC_FOLDER` to your music directory:
   ```python
   MUSIC_FOLDER = "/path/to/your/music"
   ```

## Running

```bash
python main.py
```

## Features

- **Kivy-based GUI**: Touch-friendly interface with support for Raspberry Pi displays
- **Network receiver**: Listen for incoming music requests on port 5000
- **VLC playback**: Robust audio playback with pause/skip controls
- **Queue management**: Display upcoming songs in queue
- **Keyboard controls**: Press 'Q' or ESC to quit

## Architecture

- `main.py`: Application entry point and component initialization
- `uicontroller.py`: Kivy-based UI with thread-safe updates
- `audiocontroller.py`: VLC playback controller with threading
- `receiver.py`: Network socket receiver for music commands

## Communication Protocol

Send commands to the receiver on port 5000:
- `K1`: Skip song
- `K2`: Pause
- `K3`: Resume
- Song name: Queue song for playback

## Notes

- Uses `@mainthread` decorator for thread-safe UI updates
- VLC audio output can be configured for specific devices (ALSA)
- Designed for headless Raspberry Pi setups

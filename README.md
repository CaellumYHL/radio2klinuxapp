# Radio2k

**Radio2k** is a personal, native music player designed specifically for Linux Ubuntu distros. Built with a lightweight Python backend (`PyQt6` & `pygame`), it features a striking midnight blue Tokyo aesthetic with neon accents, combined with robust functionality.

### Core Features:
- **Broad Format Support**: Native playback for FLAC, MP3, OGG, Opus, WAV, and M4A.
- **Rich Metadata Extraction**: Automatically reads track details, embedded album art (ID3/Vorbis pictures), and lazy-loads lyrics on-demand to optimize memory usage.
- **Real-Time Audio Visualizer**: A stunning, standalone 30FPS logarithmic frequency bar visualizer powered by Fast Fourier Transform (FFT/numpy).
- **Playlist Management**: Includes an automatic `~/Music` library scanner, queue manager, and the ability to create, edit, or remove custom local playlists.
- **YouTube Downloader**: Seamless integration with `yt-dlp` to directly download and append audio from YouTube into your library.
- **Advanced Playback Controls**: Supports Fisher-Yates shuffle, repeat modes (track/all/off), click-to-seek, and system-wide hardware media key integration for earbud control.

### Setup Requirements
Ensure all dependencies are met before running:
```bash
pip install -r requirements.txt
# YT-DLP required for YouTube downloads:
pip install yt-dlp
# or install via system package manager: sudo apt install yt-dlp
```

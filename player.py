"""Audio engine using pygame.mixer for FLAC playback."""

import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

import pygame
import pygame.mixer
from PyQt6.QtCore import QObject, pyqtSignal, QTimer


class Player(QObject):
    """Pygame-based audio player with Qt signals for UI updates."""
    
    # Signals
    time_changed = pyqtSignal(int)       # current position in ms
    duration_changed = pyqtSignal(int)    # total duration in ms
    track_ended = pyqtSignal()            # track finished playing
    state_changed = pyqtSignal(str)       # 'playing', 'paused', 'stopped'
    
    def __init__(self):
        super().__init__()
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=4096)
        self.current_file = None
        self._volume = 0.7
        self._is_paused = False
        self._duration_ms = 0
        self._playing = False
        
        # Seek offset tracking: pygame.mixer.music.get_pos() returns ms since
        # play() was last called. When we seek, we restart play(start=X), so
        # get_pos() resets to 0. We track the offset to compute the real position.
        self._seek_offset_ms = 0
        
        pygame.mixer.music.set_volume(self._volume)
        
        # Poll timer for position updates & end detection
        self._timer = QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._poll_position)
    
    def play(self, filepath: str):
        """Load and play a FLAC file."""
        self.current_file = filepath
        self._seek_offset_ms = 0
        self._is_paused = False
        
        try:
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            pygame.mixer.music.set_volume(self._volume)
            self._playing = True
            self._timer.start()
            self.state_changed.emit('playing')
            
            # Get duration from mutagen
            self._load_duration(filepath)
        except Exception as e:
            print(f"Error playing {filepath}: {e}")
    
    def _load_duration(self, filepath: str):
        """Get duration from file metadata."""
        try:
            from mutagen.flac import FLAC
            audio = FLAC(filepath)
            self._duration_ms = int(audio.info.length * 1000)
            self.duration_changed.emit(self._duration_ms)
        except Exception:
            self._duration_ms = 0
    
    def pause(self):
        """Pause playback."""
        if self._playing and not self._is_paused:
            pygame.mixer.music.pause()
            self._is_paused = True
            self.state_changed.emit('paused')
    
    def resume(self):
        """Resume playback."""
        if self._is_paused:
            pygame.mixer.music.unpause()
            self._is_paused = False
            self.state_changed.emit('playing')
    
    def toggle_play_pause(self):
        """Toggle between play and pause."""
        if self._is_paused:
            self.resume()
        elif self._playing:
            self.pause()
        elif self.current_file:
            self.play(self.current_file)
    
    def stop(self):
        """Stop playback."""
        pygame.mixer.music.stop()
        self._playing = False
        self._is_paused = False
        self._seek_offset_ms = 0
        self._timer.stop()
        self.state_changed.emit('stopped')
    
    def seek(self, ms: int):
        """Seek to a position in milliseconds."""
        if self.current_file and self._playing:
            seconds = max(0.0, ms / 1000.0)
            try:
                pygame.mixer.music.play(start=seconds)
                pygame.mixer.music.set_volume(self._volume)
                self._seek_offset_ms = ms
                if self._is_paused:
                    pygame.mixer.music.pause()
            except Exception as e:
                print(f"Seek error: {e}")
    
    def set_volume(self, volume: int):
        """Set volume (0-100)."""
        self._volume = max(0.0, min(1.0, volume / 100.0))
        pygame.mixer.music.set_volume(self._volume)
    
    def get_volume(self) -> int:
        return int(self._volume * 100)
    
    def get_position_ms(self) -> int:
        """Get current position in ms (accounting for seek offset)."""
        if not self._playing:
            return 0
        pos = pygame.mixer.music.get_pos()
        if pos < 0:
            return self._seek_offset_ms
        return self._seek_offset_ms + pos
    
    def get_duration_ms(self) -> int:
        """Get total duration in ms."""
        return self._duration_ms
    
    def is_playing(self) -> bool:
        return self._playing and not self._is_paused
    
    def _poll_position(self):
        """Called by timer to emit position updates and detect track end."""
        if not self._playing:
            return
        
        if not self._is_paused:
            raw_pos = pygame.mixer.music.get_pos()
            if raw_pos == -1:
                # Track ended
                self._playing = False
                self._timer.stop()
                self.track_ended.emit()
                return
            
            real_pos = self._seek_offset_ms + raw_pos
            self.time_changed.emit(real_pos)

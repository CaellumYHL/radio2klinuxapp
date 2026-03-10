"""Playlist manager — scanning, metadata, playlists, shuffle, repeat."""

import os
import json
import random
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional
from typing import Optional


MUSIC_DIR = os.path.expanduser("~/Music")
PLAYLISTS_DIR = os.path.join(os.path.dirname(__file__), "playlists")


@dataclass
class Track:
    filepath: str
    title: str
    artist: str
    album: str
    duration_ms: int  # duration in milliseconds
    
    @property
    def display_title(self) -> str:
        return self.title if self.title else os.path.splitext(os.path.basename(self.filepath))[0]
    
    @property
    def display_artist(self) -> str:
        return self.artist if self.artist else "Unknown Artist"
    
    @property
    def duration_str(self) -> str:
        total_sec = self.duration_ms // 1000
        minutes = total_sec // 60
        seconds = total_sec % 60
        return f"{minutes}:{seconds:02d}"


class RepeatMode:
    OFF = 0
    ALL = 1
    ONE = 2


class PlaylistManager:
    """Manages the track library, playlists, queue, shuffle, and repeat."""
    
    def __init__(self):
        self.all_tracks: list[Track] = []
        self.playlists: dict[str, list[str]] = {}  # name -> list of filepaths
        self.current_playlist_name: Optional[str] = None
        self.queue: list[Track] = []
        self.queue_index: int = -1
        self.shuffle_enabled: bool = False
        self.repeat_mode: int = RepeatMode.OFF
        self._shuffle_order: list[int] = []
        self._shuffle_pos: int = 0
        
        os.makedirs(PLAYLISTS_DIR, exist_ok=True)
    
    def scan_library(self) -> list[Track]:
        """Scan ~/Music for supported audio files and extract metadata."""
        self.all_tracks = []
        
        if not os.path.isdir(MUSIC_DIR):
            return self.all_tracks
            
        supported_exts = ('.flac', '.mp3', '.ogg', '.opus', '.wav', '.m4a')
        
        for filename in sorted(os.listdir(MUSIC_DIR)):
            if filename.lower().endswith(supported_exts):
                filepath = os.path.join(MUSIC_DIR, filename)
                track = self._read_track(filepath)
                if track:
                    self.all_tracks.append(track)
        
        return self.all_tracks
    
    def _read_track(self, filepath: str) -> Optional[Track]:
        """Read metadata from a supported audio file (FLAC, MP3, OGG, etc)."""
        import mutagen
        try:
            audio = mutagen.File(filepath)
            if audio is None:
                raise ValueError("Unsupported or invalid audio file")
            
            title = ""
            artist = ""
            album = ""
            
            # Helper to extract first string value from generic or ID3 tags
            def get_tag(keys):
                if not getattr(audio, 'tags', None):
                    return ""
                for k in keys:
                    if k in audio.tags:
                        val = audio.tags[k]
                        if isinstance(val, list) and len(val) > 0:
                            return str(val[0])
                        elif hasattr(val, 'text') and len(val.text) > 0:
                            return str(val.text[0])
                        else:
                            return str(val)
                return ""
            
            title = get_tag(['title', 'TIT2', 'Title'])
            artist = get_tag(['artist', 'TPE1', 'Artist'])
            album = get_tag(['album', 'TALB', 'Album'])
            
            if not title:
                title = os.path.splitext(os.path.basename(filepath))[0]
                
            duration_ms = int((audio.info.length or 0) * 1000) if getattr(audio, 'info', None) else 0
            
            return Track(
                filepath=filepath,
                title=title,
                artist=artist,
                album=album,
                duration_ms=duration_ms,
            )
        except Exception as e:
            # Fallback for files with no/bad metadata
            basename = os.path.splitext(os.path.basename(filepath))[0]
            return Track(
                filepath=filepath,
                title=basename,
                artist="",
                album="",
                duration_ms=0,
            )
    
    # --- Queue management ---
    
    def set_queue(self, tracks: list[Track], start_index: int = 0):
        """Set the playback queue."""
        self.queue = list(tracks)
        self.queue_index = start_index
        if self.shuffle_enabled:
            self._generate_shuffle_order()
    
    def get_current_track(self) -> Optional[Track]:
        """Get the currently selected track."""
        if 0 <= self.queue_index < len(self.queue):
            if self.shuffle_enabled and self._shuffle_order:
                idx = self._shuffle_order[self._shuffle_pos]
                return self.queue[idx]
            return self.queue[self.queue_index]
        return None
    
    def next_track(self) -> Optional[Track]:
        """Advance to the next track based on repeat/shuffle mode."""
        if not self.queue:
            return None
        
        if self.repeat_mode == RepeatMode.ONE:
            return self.get_current_track()
        
        if self.shuffle_enabled:
            self._shuffle_pos += 1
            if self._shuffle_pos >= len(self._shuffle_order):
                if self.repeat_mode == RepeatMode.ALL:
                    self._generate_shuffle_order()
                    return self.get_current_track()
                return None
            return self.get_current_track()
        else:
            self.queue_index += 1
            if self.queue_index >= len(self.queue):
                if self.repeat_mode == RepeatMode.ALL:
                    self.queue_index = 0
                    return self.get_current_track()
                self.queue_index = len(self.queue) - 1
                return None
            return self.get_current_track()
    
    def prev_track(self) -> Optional[Track]:
        """Go to the previous track."""
        if not self.queue:
            return None
        
        if self.shuffle_enabled:
            self._shuffle_pos = max(0, self._shuffle_pos - 1)
            return self.get_current_track()
        else:
            self.queue_index = max(0, self.queue_index - 1)
            return self.get_current_track()
    
    def play_track_at(self, index: int) -> Optional[Track]:
        """Play a specific track by index in the current queue."""
        if 0 <= index < len(self.queue):
            if self.shuffle_enabled:
                # Find this index in shuffle order or just set it
                if index in self._shuffle_order:
                    self._shuffle_pos = self._shuffle_order.index(index)
                else:
                    self.queue_index = index
            else:
                self.queue_index = index
            return self.queue[index]
        return None
    
    # --- Shuffle ---
    
    def toggle_shuffle(self) -> bool:
        """Toggle shuffle mode. Returns new state."""
        self.shuffle_enabled = not self.shuffle_enabled
        if self.shuffle_enabled:
            self._generate_shuffle_order()
        return self.shuffle_enabled
    
    def _generate_shuffle_order(self):
        """Generate a shuffled index order (Fisher-Yates)."""
        self._shuffle_order = list(range(len(self.queue)))
        # Put current track first so it doesn't restart
        current = self.queue_index if self.queue_index >= 0 else 0
        if current in self._shuffle_order:
            self._shuffle_order.remove(current)
        random.shuffle(self._shuffle_order)
        self._shuffle_order.insert(0, current)
        self._shuffle_pos = 0
    
    # --- Repeat ---
    
    def cycle_repeat(self) -> int:
        """Cycle through repeat modes. Returns new mode."""
        self.repeat_mode = (self.repeat_mode + 1) % 3
        return self.repeat_mode
    
    # --- Playlist CRUD ---
    
    def load_playlists(self):
        """Load all saved playlists from disk."""
        self.playlists = {}
        for filename in os.listdir(PLAYLISTS_DIR):
            if filename.endswith('.json'):
                name = filename[:-5]
                filepath = os.path.join(PLAYLISTS_DIR, filename)
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                    self.playlists[name] = data.get('tracks', [])
                except Exception:
                    pass
    
    def create_playlist(self, name: str):
        """Create a new empty playlist."""
        self.playlists[name] = []
        self._save_playlist(name)
    
    def delete_playlist(self, name: str):
        """Delete a playlist."""
        if name in self.playlists:
            del self.playlists[name]
            filepath = os.path.join(PLAYLISTS_DIR, f"{name}.json")
            if os.path.exists(filepath):
                os.remove(filepath)
    
    def rename_playlist(self, old_name: str, new_name: str):
        """Rename a playlist."""
        if old_name in self.playlists:
            self.playlists[new_name] = self.playlists.pop(old_name)
            old_path = os.path.join(PLAYLISTS_DIR, f"{old_name}.json")
            if os.path.exists(old_path):
                os.remove(old_path)
            self._save_playlist(new_name)
    
    def add_to_playlist(self, playlist_name: str, filepath: str):
        """Add a track to a playlist."""
        if playlist_name in self.playlists:
            if filepath not in self.playlists[playlist_name]:
                self.playlists[playlist_name].append(filepath)
                self._save_playlist(playlist_name)
    
    def remove_from_playlist(self, playlist_name: str, filepath: str):
        """Remove a track from a playlist."""
        if playlist_name in self.playlists:
            if filepath in self.playlists[playlist_name]:
                self.playlists[playlist_name].remove(filepath)
                self._save_playlist(playlist_name)
    
    def get_playlist_tracks(self, name: str) -> list[Track]:
        """Get Track objects for a playlist."""
        if name not in self.playlists:
            return []
        track_map = {t.filepath: t for t in self.all_tracks}
        return [track_map[fp] for fp in self.playlists[name] if fp in track_map]
    
    def _save_playlist(self, name: str):
        """Save a playlist to disk."""
        filepath = os.path.join(PLAYLISTS_DIR, f"{name}.json")
        data = {'name': name, 'tracks': self.playlists.get(name, [])}
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

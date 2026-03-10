"""Radio2k — PyQt6 main window and all UI widgets."""

import os
import sys
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSlider, QListWidget, QListWidgetItem, QSplitter,
    QFrame, QInputDialog, QMenu, QMessageBox, QSizePolicy,
    QGraphicsDropShadowEffect, QApplication, QStyleOptionSlider, QStyle,
    QDialog, QTextEdit
)
from PyQt6.QtGui import (
    QPixmap, QPainter, QColor, QFont, QFontDatabase, QIcon,
    QPalette, QLinearGradient, QBrush, QPen, QAction, QCursor, QShortcut, QKeySequence
)
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal, QPoint, QPointF, QRect

from player import Player
from playlist import PlaylistManager, Track, RepeatMode
from visualizer import VisualizerWindow

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")


def ms_to_str(ms: int) -> str:
    """Convert milliseconds to MM:SS string."""
    total_sec = max(0, ms // 1000)
    return f"{total_sec // 60}:{total_sec % 60:02d}"


class ClickableSlider(QSlider):
    """A slider that jumps to the clicked position instead of paging."""
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            opt = QStyleOptionSlider()
            self.initStyleOption(opt)
            groove = self.style().subControlRect(
                QStyle.ComplexControl.CC_Slider, opt,
                QStyle.SubControl.SC_SliderGroove, self
            )
            if self.orientation() == Qt.Orientation.Horizontal:
                pos = event.position().x()
                val = QStyle.sliderValueFromPosition(
                    self.minimum(), self.maximum(),
                    int(pos - groove.x()), groove.width()
                )
            else:
                pos = event.position().y()
                val = QStyle.sliderValueFromPosition(
                    self.minimum(), self.maximum(),
                    int(pos - groove.y()), groove.height()
                )
            self.setValue(val)
            self.sliderMoved.emit(val)
            event.accept()
        super().mousePressEvent(event)


def extract_lyrics(filepath: str) -> str:
    """Extract embedded lyrics from an audio file."""
    try:
        import mutagen
        audio = mutagen.File(filepath)
        if hasattr(audio, 'tags') and audio.tags:
            # FLAC / OGG
            for key in ['lyrics', 'unsyncedlyrics', 'LYRICS', 'UNSYNCEDLYRICS']:
                if key in audio.tags:
                    val = audio.tags[key]
                    if isinstance(val, list):
                        return "\n".join(val)
                    return str(val)
                    
            # ID3 (MP3)
            for key in audio.tags.keys():
                if key.startswith('USLT'):
                    return str(audio.tags[key].text)
                    
    except Exception:
        pass
    return "No lyrics found in this file metadata."


class LyricsDialog(QDialog):
    """Simple dialog to display track lyrics on demand."""
    def __init__(self, title, lyrics, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"⛧ {title} — Lyrcis")
        self.setMinimumSize(400, 500)
        self.setStyleSheet("background-color: #111111; color: #c0c0c0; border: 1px solid #333;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setText(lyrics)
        text_edit.setStyleSheet("border: none; font-size: 14px; padding: 15px; background: transparent;")
        
        # Center align lyrics
        text_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(text_edit)


def extract_album_art(filepath: str) -> QPixmap | None:
    """Extract embedded album art from an audio file."""
    try:
        import mutagen
        audio = mutagen.File(filepath)
        
        # FLAC
        if hasattr(audio, 'pictures') and audio.pictures:
            pic = audio.pictures[0]
            pixmap = QPixmap()
            pixmap.loadFromData(pic.data)
            if not pixmap.isNull():
                return pixmap
                
        # ID3 (MP3)
        if hasattr(audio, 'tags') and audio.tags:
            for key in audio.tags.keys():
                if key.startswith('APIC'):
                    pixmap = QPixmap()
                    pixmap.loadFromData(audio.tags[key].data)
                    if not pixmap.isNull():
                        return pixmap
                        
            # OGG 
            if 'metadata_block_picture' in audio.tags:
                import base64
                from mutagen.flac import Picture
                for b64_data in audio.tags['metadata_block_picture']:
                    try:
                        p = Picture(base64.b64decode(b64_data))
                        pixmap = QPixmap()
                        pixmap.loadFromData(p.data)
                        if not pixmap.isNull():
                            return pixmap
                    except Exception:
                        pass
    except Exception:
        pass
    return None


class GothicDivider(QFrame):
    """A decorative gothic divider using the wing asset."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        wing_path = os.path.join(ASSETS_DIR, "04_chrome_shape.png")
        if os.path.exists(wing_path):
            self._pixmap = QPixmap(wing_path)
        else:
            self._pixmap = None
    
    def paintEvent(self, event):
        if self._pixmap:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            scaled = self._pixmap.scaledToWidth(
                min(self.width() - 40, 500),
                Qt.TransformationMode.SmoothTransformation
            )
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.setOpacity(0.4)
            painter.drawPixmap(x, y, scaled)
            painter.end()


class NowPlayingArt(QLabel):
    """Album art display with barbed wire circle frame overlay."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(280, 280)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background: transparent;")
        
        # Load barbed wire frame
        wire_path = os.path.join(ASSETS_DIR, "01_chrome_shape.png")
        self._wire = QPixmap(wire_path) if os.path.exists(wire_path) else None
        self._album_art: QPixmap | None = None
        self._glow_opacity = 0.6
    
    def set_album_art(self, pixmap: QPixmap | None):
        """Set album art pixmap, or None for default."""
        self._album_art = pixmap
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        cx, cy = self.width() // 2, self.height() // 2
        radius = min(self.width(), self.height()) // 2 - 10
        
        # Dark circle background
        painter.setBrush(QBrush(QColor(15, 15, 15)))
        painter.setPen(QPen(QColor(212, 160, 23, 40), 1))
        painter.drawEllipse(QPoint(cx, cy), radius, radius)
        
        # Draw album art (or fallback) inside the circle
        if self._album_art and not self._album_art.isNull():
            # Clip to circle
            from PyQt6.QtGui import QPainterPath
            clip_path = QPainterPath()
            clip_path.addEllipse(QPointF(cx, cy), radius - 2, radius - 2)
            painter.setClipPath(clip_path)
            
            art_size = radius * 2 - 4
            scaled = self._album_art.scaled(
                art_size, art_size,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            # Center crop
            x_off = (scaled.width() - art_size) // 2
            y_off = (scaled.height() - art_size) // 2
            cropped = scaled.copy(x_off, y_off, art_size, art_size)
            
            painter.setOpacity(0.9)
            painter.drawPixmap(cx - art_size // 2, cy - art_size // 2, cropped)
            painter.setOpacity(1.0)
            painter.setClipping(False)
        else:
            # Fallback: draw a subtle placeholder
            painter.setOpacity(0.3)
            painter.setPen(QPen(QColor(212, 160, 23, 60), 1))
            painter.setFont(QFont("Serif", 36))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "♫")
            painter.setOpacity(1.0)
        
        # Barbed wire circle overlay
        if self._wire:
            wire_size = radius * 2 + 15
            scaled_wire = self._wire.scaled(
                wire_size, wire_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            wx = cx - scaled_wire.width() // 2
            wy = cy - scaled_wire.height() // 2
            painter.setOpacity(self._glow_opacity)
            painter.drawPixmap(wx, wy, scaled_wire)
        
        painter.end()


class TrackListWidget(QListWidget):
    """Custom styled track list with single-click to play."""
    track_clicked = pyqtSignal(int)
    add_to_playlist_requested = pyqtSignal(int, str)  # track_index, playlist_name
    remove_from_playlist_requested = pyqtSignal(int)  # track_index
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.itemClicked.connect(self._on_click)
        self.playlist_names: list[str] = []
        self.current_playlist: str | None = None
        self._tracks: list[Track] = []
    
    def set_tracks(self, tracks: list[Track]):
        """Populate the list with tracks."""
        self._tracks = tracks
        self.clear()
        for i, track in enumerate(tracks):
            item = QListWidgetItem()
            display = f"  {track.display_title}"
            if track.display_artist and track.display_artist != "Unknown Artist":
                display += f"  —  {track.display_artist}"
            display += f"    [{track.duration_str}]"
            item.setText(display)
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.addItem(item)
    
    def highlight_track(self, index: int):
        """Highlight the currently playing track."""
        for i in range(self.count()):
            item = self.item(i)
            if i == index:
                item.setForeground(QColor(212, 160, 23))
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            else:
                item.setForeground(QColor(180, 180, 180))
                font = item.font()
                font.setBold(False)
                item.setFont(font)
    
    def _on_click(self, item: QListWidgetItem):
        index = item.data(Qt.ItemDataRole.UserRole)
        if index is not None:
            self.track_clicked.emit(index)
    
    def _show_context_menu(self, pos):
        item = self.itemAt(pos)
        if not item:
            return
        index = item.data(Qt.ItemDataRole.UserRole)
        
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: #1a1a1a;
                color: #c0c0c0;
                border: 1px solid #333;
                padding: 4px;
            }
            QMenu::item:selected {
                background: #d4a017;
                color: #0a0a0a;
            }
        """)
        
        if self.playlist_names:
            add_menu = menu.addMenu("Add to Playlist")
            for name in self.playlist_names:
                action = add_menu.addAction(name)
                action.triggered.connect(
                    lambda checked, n=name, i=index: self.add_to_playlist_requested.emit(i, n)
                )
                
        if self.current_playlist and self.current_playlist != "__all__":
            menu.addSeparator()
            remove_action = menu.addAction("Remove from Playlist")
            remove_action.triggered.connect(
                lambda checked, idx=index: self.remove_from_playlist_requested.emit(idx)
            )
        
        menu.exec(self.mapToGlobal(pos))


class GothicPlayerWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("⛧ RADIO2K ⛧")
        self.setMinimumSize(1000, 700)
        self.resize(1100, 750)
        
        # Core components
        self.player = Player()
        self.playlist_mgr = PlaylistManager()
        self.visualizer_window = None
        
        # State
        self._current_duration = 0
        self._seeking = False
        
        # Build UI
        self._build_ui()
        self._connect_signals()
        
        # Load data
        self._load_data()
    
    def _build_ui(self):
        """Construct the entire UI layout."""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # === HEADER ===
        header = self._build_header()
        main_layout.addWidget(header)
        
        # === GOTHIC DIVIDER ===
        self.divider = GothicDivider()
        main_layout.addWidget(self.divider)
        
        # === MAIN CONTENT (sidebar + now playing) ===
        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        content_splitter.setHandleWidth(1)
        content_splitter.setStyleSheet("QSplitter::handle { background: #2a2a2a; }")
        
        sidebar = self._build_sidebar()
        now_playing_panel = self._build_now_playing()
        
        content_splitter.addWidget(sidebar)
        content_splitter.addWidget(now_playing_panel)
        content_splitter.setSizes([320, 780])
        content_splitter.setStretchFactor(0, 0)
        content_splitter.setStretchFactor(1, 1)
        
        main_layout.addWidget(content_splitter, 1)
        
        # === CONTROL BAR ===
        controls = self._build_controls()
        main_layout.addWidget(controls)
    
    def _build_header(self) -> QWidget:
        """Build the header with title and planet dither graphic."""
        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(80)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 10, 20, 10)
        
        # Title
        title = QLabel("⛧ RADIO2K")
        title.setObjectName("headerTitle")
        title.setFont(QFont("Serif", 22, QFont.Weight.Bold))
        layout.addWidget(title)
        
        layout.addStretch()
        
        # Planet dither graphic in top right
        planet_path = os.path.join(ASSETS_DIR, "planet_dither.png")
        if os.path.exists(planet_path):
            planet_label = QLabel()
            pix = QPixmap(planet_path).scaledToHeight(
                60, Qt.TransformationMode.SmoothTransformation
            )
            planet_label.setPixmap(pix)
            planet_label.setStyleSheet("background: transparent;")
            planet_label.setOpacity = 0.7
            layout.addWidget(planet_label)
        
        return header
    
    def _build_sidebar(self) -> QWidget:
        """Build the left sidebar with playlists and track list."""
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setMinimumWidth(280)
        sidebar.setMaximumWidth(400)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        # Playlists section
        pl_header = QHBoxLayout()
        pl_label = QLabel("PLAYLISTS")
        pl_label.setObjectName("sectionLabel")
        pl_header.addWidget(pl_label)
        pl_header.addStretch()
        
        self.btn_new_playlist = QPushButton("+ NEW")
        self.btn_new_playlist.setObjectName("smallButton")
        self.btn_new_playlist.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        pl_header.addWidget(self.btn_new_playlist)
        layout.addLayout(pl_header)
        
        self.playlist_list = QListWidget()
        self.playlist_list.setObjectName("playlistList")
        self.playlist_list.setMaximumHeight(150)
        self.playlist_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        layout.addWidget(self.playlist_list)
        
        # Tracks section
        tracks_label = QLabel("TRACKS")
        tracks_label.setObjectName("sectionLabel")
        layout.addWidget(tracks_label)
        
        self.track_list = TrackListWidget()
        self.track_list.setObjectName("trackList")
        layout.addWidget(self.track_list, 1)
        
        return sidebar
    
    def _build_now_playing(self) -> QWidget:
        """Build the now-playing panel."""
        panel = QFrame()
        panel.setObjectName("nowPlayingPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(15)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Art
        self.art_widget = NowPlayingArt()
        layout.addWidget(self.art_widget, 0, Qt.AlignmentFlag.AlignCenter)
        
        # Track info
        self.lbl_track_title = QLabel("No Track Selected")
        self.lbl_track_title.setObjectName("trackTitle")
        self.lbl_track_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_track_title.setWordWrap(True)
        layout.addWidget(self.lbl_track_title)
        
        self.lbl_track_artist = QLabel("")
        self.lbl_track_artist.setObjectName("trackArtist")
        self.lbl_track_artist.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_track_artist)
        
        # Seek bar area
        seek_layout = QVBoxLayout()
        seek_layout.setSpacing(4)
        
        self.seek_slider = ClickableSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setObjectName("seekSlider")
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        seek_layout.addWidget(self.seek_slider)
        
        time_layout = QHBoxLayout()
        self.lbl_time_current = QLabel("0:00")
        self.lbl_time_current.setObjectName("timeLabel")
        self.lbl_time_total = QLabel("0:00")
        self.lbl_time_total.setObjectName("timeLabel")
        time_layout.addWidget(self.lbl_time_current)
        time_layout.addStretch()
        time_layout.addWidget(self.lbl_time_total)
        seek_layout.addLayout(time_layout)
        
        layout.addLayout(seek_layout)
        layout.addStretch()
        
        return panel
    
    def _build_controls(self) -> QWidget:
        """Build the bottom control bar."""
        bar = QFrame()
        bar.setObjectName("controlBar")
        bar.setFixedHeight(70)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(20, 8, 20, 8)
        layout.setSpacing(12)
        
        # Transport controls
        self.btn_prev = QPushButton("⏮")
        self.btn_prev.setObjectName("transportBtn")
        self.btn_prev.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
        self.btn_play = QPushButton("▶")
        self.btn_play.setObjectName("playBtn")
        self.btn_play.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
        self.btn_next = QPushButton("⏭")
        self.btn_next.setObjectName("transportBtn")
        self.btn_next.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
        layout.addWidget(self.btn_prev)
        layout.addWidget(self.btn_play)
        layout.addWidget(self.btn_next)
        
        # Spacer
        layout.addSpacing(20)
        
        # Shuffle & Repeat
        self.btn_shuffle = QPushButton("🔀")
        self.btn_shuffle.setObjectName("modeBtn")
        self.btn_shuffle.setCheckable(True)
        self.btn_shuffle.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
        self.btn_repeat = QPushButton("🔁")
        self.btn_repeat.setObjectName("modeBtn")
        self.btn_repeat.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
        # Lyrics & Visualizer
        self.btn_lyrics = QPushButton("📜 LYRICS")
        self.btn_lyrics.setObjectName("smallButton")
        self.btn_lyrics.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
        self.btn_visualizer = QPushButton("👁 VISUALIZER")
        self.btn_visualizer.setObjectName("smallButton")
        self.btn_visualizer.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
        layout.addWidget(self.btn_shuffle)
        layout.addWidget(self.btn_repeat)
        layout.addWidget(self.btn_lyrics)
        layout.addWidget(self.btn_visualizer)
        
        layout.addStretch()
        
        # Now playing mini info
        self.lbl_mini_title = QLabel("")
        self.lbl_mini_title.setObjectName("miniTitle")
        self.lbl_mini_title.setMaximumWidth(300)
        layout.addWidget(self.lbl_mini_title)
        
        layout.addStretch()
        
        # Volume
        vol_icon = QLabel("🔊")
        vol_icon.setObjectName("volIcon")
        layout.addWidget(vol_icon)
        
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setObjectName("volumeSlider")
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_slider.setFixedWidth(120)
        self.volume_slider.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        layout.addWidget(self.volume_slider)
        
        return bar
    
    def _connect_signals(self):
        """Wire up all signals and slots."""
        # Player signals
        self.player.time_changed.connect(self._on_time_changed)
        self.player.duration_changed.connect(self._on_duration_changed)
        self.player.track_ended.connect(self._on_track_ended)
        self.player.state_changed.connect(self._on_state_changed)
        
        # Transport
        self.btn_play.clicked.connect(self._on_play_clicked)
        self.btn_next.clicked.connect(self._on_next)
        self.btn_prev.clicked.connect(self._on_prev)
        
        # Modes
        self.btn_shuffle.clicked.connect(self._on_shuffle_toggle)
        self.btn_repeat.clicked.connect(self._on_repeat_cycle)
        self.btn_lyrics.clicked.connect(self._on_lyrics_clicked)
        self.btn_visualizer.clicked.connect(self._on_visualizer_clicked)
        
        # Media Keys
        QShortcut(QKeySequence(Qt.Key.Key_MediaPlay), self, self._on_play_clicked)
        QShortcut(QKeySequence(Qt.Key.Key_MediaPause), self, self._on_play_clicked)
        QShortcut(QKeySequence(Qt.Key.Key_MediaTogglePlayPause), self, self._on_play_clicked)
        QShortcut(QKeySequence(Qt.Key.Key_MediaNext), self, self._on_next)
        QShortcut(QKeySequence(Qt.Key.Key_MediaPrevious), self, self._on_prev)
        
        # Seek — click anywhere or drag to seek
        self.seek_slider.sliderPressed.connect(lambda: setattr(self, '_seeking', True))
        self.seek_slider.sliderReleased.connect(self._on_seek_released)
        self.seek_slider.sliderMoved.connect(self._on_seek_moved)
        
        # Volume
        self.volume_slider.valueChanged.connect(self.player.set_volume)
        
        # Track list — single click to play
        self.track_list.track_clicked.connect(self._on_track_selected)
        self.track_list.add_to_playlist_requested.connect(self._on_add_to_playlist)
        self.track_list.remove_from_playlist_requested.connect(self._on_remove_from_playlist)
        
        # Playlist list
        self.playlist_list.itemClicked.connect(self._on_playlist_clicked)
        self.playlist_list.customContextMenuRequested.connect(self._on_playlist_context_menu)
        self.btn_new_playlist.clicked.connect(self._on_new_playlist)
    
    def _load_data(self):
        """Scan library and load playlists."""
        tracks = self.playlist_mgr.scan_library()
        self.track_list.set_tracks(tracks)
        
        # Load playlists
        self.playlist_mgr.load_playlists()
        self._refresh_playlist_list()
        
        # Set initial queue to all tracks
        self.playlist_mgr.set_queue(tracks)
        
        # Add "All Tracks" as default selection
        self.track_list.current_playlist = "__all__"
        all_item = QListWidgetItem("  ♫  All Tracks")
        all_item.setData(Qt.ItemDataRole.UserRole, "__all__")
        self.playlist_list.insertItem(0, all_item)
        self.playlist_list.setCurrentRow(0)
    
    def _refresh_playlist_list(self):
        """Refresh the playlist sidebar."""
        self.playlist_list.clear()
        
        # All tracks entry
        all_item = QListWidgetItem("  ♫  All Tracks")
        all_item.setData(Qt.ItemDataRole.UserRole, "__all__")
        self.playlist_list.addItem(all_item)
        
        for name in sorted(self.playlist_mgr.playlists.keys()):
            item = QListWidgetItem(f"  ▸  {name}")
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.playlist_list.addItem(item)
        
        # Update track list context menu
        self.track_list.playlist_names = list(self.playlist_mgr.playlists.keys())
    
    # === Player event handlers ===
    
    def _on_time_changed(self, ms: int):
        if not self._seeking:
            self.lbl_time_current.setText(ms_to_str(ms))
            if self._current_duration > 0:
                self.seek_slider.setValue(int(ms / self._current_duration * 1000))
    
    def _on_duration_changed(self, ms: int):
        self._current_duration = ms
        self.lbl_time_total.setText(ms_to_str(ms))
    
    def _on_track_ended(self):
        track = self.playlist_mgr.next_track()
        if track:
            self._play_track(track)
        else:
            self.btn_play.setText("▶")
            self.lbl_mini_title.setText("")
    
    def _on_state_changed(self, state: str):
        if state == 'playing':
            self.btn_play.setText("⏸")
        else:
            self.btn_play.setText("▶")
    
    # === Control handlers ===
    
    def _on_play_clicked(self):
        if self.player.is_playing():
            self.player.pause()
        elif self.player.current_file:
            self.player.toggle_play_pause()
        else:
            # Start playing first track
            track = self.playlist_mgr.get_current_track()
            if not track and self.playlist_mgr.queue:
                self.playlist_mgr.queue_index = 0
                track = self.playlist_mgr.get_current_track()
            if track:
                self._play_track(track)
    
    def _on_next(self):
        track = self.playlist_mgr.next_track()
        if track:
            self._play_track(track)
    
    def _on_prev(self):
        # If more than 3 seconds in, restart current track
        if self.player.get_position_ms() > 3000:
            self.player.seek(0)
            return
        track = self.playlist_mgr.prev_track()
        if track:
            self._play_track(track)
    
    def _on_seek_released(self):
        self._seeking = False
        if self._current_duration > 0:
            ratio = self.seek_slider.value() / 1000.0
            target_ms = int(ratio * self._current_duration)
            self.player.seek(target_ms)
            self.lbl_time_current.setText(ms_to_str(target_ms))
    
    def _on_seek_moved(self, value: int):
        """Seek immediately when the slider is clicked or dragged."""
        self._seeking = True
        if self._current_duration > 0:
            ratio = value / 1000.0
            target_ms = int(ratio * self._current_duration)
            self.player.seek(target_ms)
            self.lbl_time_current.setText(ms_to_str(target_ms))
        self._seeking = False
    
    def _on_shuffle_toggle(self):
        enabled = self.playlist_mgr.toggle_shuffle()
        self.btn_shuffle.setChecked(enabled)
        if enabled:
            self.btn_shuffle.setStyleSheet("color: #d4a017; border-color: #d4a017;")
        else:
            self.btn_shuffle.setStyleSheet("")
    
    def _on_repeat_cycle(self):
        mode = self.playlist_mgr.cycle_repeat()
        labels = {
            RepeatMode.OFF: "🔁",
            RepeatMode.ALL: "🔁",  
            RepeatMode.ONE: "🔂",
        }
        self.btn_repeat.setText(labels.get(mode, "🔁"))
        if mode == RepeatMode.OFF:
            self.btn_repeat.setStyleSheet("")
        elif mode == RepeatMode.ALL:
            self.btn_repeat.setStyleSheet("color: #d4a017; border-color: #d4a017;")
        elif mode == RepeatMode.ONE:
            self.btn_repeat.setStyleSheet("color: #e8a020; border-color: #e8a020;")
            
    def _on_lyrics_clicked(self):
        track = self.playlist_mgr.get_current_track()
        if track:
            lyrics = extract_lyrics(track.filepath)
            dialog = LyricsDialog(track.display_title, lyrics, self)
            dialog.exec()
            
    def _on_visualizer_clicked(self):
        if not self.visualizer_window:
            self.visualizer_window = VisualizerWindow(self.player)
        self.visualizer_window.show()
        self.visualizer_window.raise_()
        self.visualizer_window.activateWindow()
    
    def _on_track_selected(self, index: int):
        """User clicked a track in the list."""
        track = self.playlist_mgr.play_track_at(index)
        if track:
            self._play_track(track)
    
    def _play_track(self, track: Track):
        """Play a track and update all UI elements."""
        self.player.play(track.filepath)
        self.lbl_track_title.setText(track.display_title)
        self.lbl_track_artist.setText(track.display_artist)
        self.lbl_mini_title.setText(track.display_title)
        self.lbl_time_total.setText(track.duration_str)
        self._current_duration = track.duration_ms
        self.seek_slider.setValue(0)
        
        # Update album art
        art = extract_album_art(track.filepath)
        self.art_widget.set_album_art(art)
        
        # Highlight in list
        idx = -1
        for i, t in enumerate(self.playlist_mgr.queue):
            if t.filepath == track.filepath:
                idx = i
                break
        self.track_list.highlight_track(idx)
    
    # === Playlist handlers ===
    
    def _on_playlist_clicked(self, item: QListWidgetItem):
        name = item.data(Qt.ItemDataRole.UserRole)
        self.track_list.current_playlist = name
        if name == "__all__":
            self.track_list.set_tracks(self.playlist_mgr.all_tracks)
            self.playlist_mgr.set_queue(self.playlist_mgr.all_tracks)
        else:
            tracks = self.playlist_mgr.get_playlist_tracks(name)
            self.track_list.set_tracks(tracks)
            self.playlist_mgr.set_queue(tracks)
    
    def _on_new_playlist(self):
        name, ok = QInputDialog.getText(
            self, "New Playlist", "Enter playlist name:",
        )
        if ok and name.strip():
            self.playlist_mgr.create_playlist(name.strip())
            self._refresh_playlist_list()
    
    def _on_playlist_context_menu(self, pos):
        item = self.playlist_list.itemAt(pos)
        if not item:
            return
        name = item.data(Qt.ItemDataRole.UserRole)
        if name == "__all__":
            return
        
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: #1a1a1a;
                color: #c0c0c0;
                border: 1px solid #333;
                padding: 4px;
            }
            QMenu::item:selected {
                background: #d4a017;
                color: #0a0a0a;
            }
        """)
        
        rename_action = menu.addAction("Rename")
        delete_action = menu.addAction("Delete")
        
        action = menu.exec(self.playlist_list.mapToGlobal(pos))
        if action == rename_action:
            new_name, ok = QInputDialog.getText(
                self, "Rename Playlist", "New name:", text=name
            )
            if ok and new_name.strip():
                self.playlist_mgr.rename_playlist(name, new_name.strip())
                self._refresh_playlist_list()
        elif action == delete_action:
            self.playlist_mgr.delete_playlist(name)
            self._refresh_playlist_list()
    
    def _on_add_to_playlist(self, track_index: int, playlist_name: str):
        """Add a track to a specific playlist."""
        if track_index < len(self.playlist_mgr.queue):
            track = self.playlist_mgr.queue[track_index]
            self.playlist_mgr.add_to_playlist(playlist_name, track.filepath)

    def _on_remove_from_playlist(self, track_index: int):
        """Remove a track from the currently active playlist."""
        playlist_name = self.track_list.current_playlist
        if not playlist_name or playlist_name == "__all__":
            return
            
        if track_index < len(self.playlist_mgr.queue):
            track = self.playlist_mgr.queue[track_index]
            self.playlist_mgr.remove_from_playlist(playlist_name, track.filepath)
            
            # Refresh view to instantly show removal
            tracks = self.playlist_mgr.get_playlist_tracks(playlist_name)
            self.track_list.set_tracks(tracks)
            self.playlist_mgr.set_queue(tracks)

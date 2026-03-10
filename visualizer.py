"""Radio2k Visualizer — FFT-based frequency bar visualization.

Lazy-loaded: only loads audio data when the visualizer window is opened.
Uses pygame.mixer.Sound to decode FLAC to raw samples, then numpy for FFT.
"""

import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

import numpy as np
import pygame
import pygame.mixer
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton
from PyQt6.QtGui import QPainter, QColor, QLinearGradient, QPen, QBrush, QFont
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF


# Number of frequency bars to display
NUM_BARS = 48
# FFT window size
FFT_SIZE = 4096
# Sample rate (must match pygame mixer init)
SAMPLE_RATE = 44100


class VisualizerWidget(QWidget):
    """A widget that draws FFT frequency bars synchronized to audio playback."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(600, 300)
        self._bars = np.zeros(NUM_BARS)
        self._smoothed_bars = np.zeros(NUM_BARS)
        self._peak_bars = np.zeros(NUM_BARS)
        self._samples = None
        self._channels = 2
        self._loaded_file = None

        # Colors
        self._color_low = QColor(212, 160, 23)      # Amber
        self._color_mid = QColor(232, 120, 20)       # Orange
        self._color_high = QColor(200, 50, 50)       # Red
        self._bg_color = QColor(8, 8, 8)
        self._peak_color = QColor(212, 160, 23, 180)

    def load_audio(self, filepath: str):
        """Load audio samples from a file. Only call when visualizer is visible."""
        if self._loaded_file == filepath and self._samples is not None:
            return  # Already loaded

        try:
            sound = pygame.mixer.Sound(filepath)
            raw = sound.get_raw()
            # pygame mixer is init'd at 44100, 16-bit signed, stereo
            self._samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
            self._channels = 2
            self._loaded_file = filepath
            # Free the Sound object, we have the raw data
            del sound
        except Exception as e:
            print(f"Visualizer: could not load audio: {e}")
            self._samples = None

    def unload_audio(self):
        """Free audio data from memory."""
        self._samples = None
        self._loaded_file = None
        self._bars = np.zeros(NUM_BARS)
        self._smoothed_bars = np.zeros(NUM_BARS)
        self._peak_bars = np.zeros(NUM_BARS)

    def update_frame(self, position_ms: int):
        """Compute FFT bars for the current playback position."""
        if self._samples is None:
            return

        # Convert position to sample index
        sample_idx = int((position_ms / 1000.0) * SAMPLE_RATE) * self._channels
        end_idx = sample_idx + FFT_SIZE * self._channels

        if sample_idx < 0 or end_idx > len(self._samples):
            return

        # Extract mono chunk (average channels)
        chunk = self._samples[sample_idx:end_idx]
        if self._channels == 2:
            chunk = chunk.reshape(-1, 2).mean(axis=1)

        if len(chunk) < FFT_SIZE:
            return

        # Apply Hanning window and compute FFT
        windowed = chunk[:FFT_SIZE] * np.hanning(FFT_SIZE)
        fft_data = np.abs(np.fft.rfft(windowed))

        # Convert to log scale
        fft_data = np.where(fft_data > 0, 20 * np.log10(fft_data + 1e-10), 0)

        # Group into bars (logarithmic frequency distribution)
        freq_bins = len(fft_data)
        bar_values = np.zeros(NUM_BARS)

        for i in range(NUM_BARS):
            # Logarithmic mapping: more bars for low frequencies
            low = int(freq_bins * (2 ** (i / NUM_BARS * 10) - 1) / (2 ** 10 - 1))
            high = int(freq_bins * (2 ** ((i + 1) / NUM_BARS * 10) - 1) / (2 ** 10 - 1))
            high = max(high, low + 1)
            high = min(high, freq_bins)
            if low < freq_bins:
                bar_values[i] = np.mean(fft_data[low:high])

        # Normalize (0 to 1)
        max_val = np.max(bar_values) if np.max(bar_values) > 0 else 1
        self._bars = np.clip(bar_values / max_val, 0, 1)

        # Smooth animation (bars fall down slowly)
        self._smoothed_bars = np.maximum(
            self._bars,
            self._smoothed_bars * 0.85
        )

        # Peak indicators (fall slowly)
        self._peak_bars = np.maximum(self._bars, self._peak_bars * 0.97)

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()

        # Background
        painter.fillRect(0, 0, w, h, self._bg_color)

        if NUM_BARS == 0:
            return

        # Bar geometry
        margin = 20
        bar_area_w = w - margin * 2
        bar_area_h = h - margin * 2
        bar_width = max(2, (bar_area_w / NUM_BARS) * 0.75)
        bar_gap = bar_area_w / NUM_BARS
        base_y = h - margin

        for i in range(NUM_BARS):
            bar_h = self._smoothed_bars[i] * bar_area_h
            x = margin + i * bar_gap + (bar_gap - bar_width) / 2
            y = base_y - bar_h

            if bar_h < 1:
                continue

            # Gradient fill per bar
            gradient = QLinearGradient(QPointF(x, base_y), QPointF(x, y))
            # Intensity-based coloring
            intensity = self._smoothed_bars[i]
            if intensity < 0.4:
                gradient.setColorAt(0, QColor(100, 75, 10, 200))
                gradient.setColorAt(1, self._color_low)
            elif intensity < 0.7:
                gradient.setColorAt(0, QColor(140, 80, 10, 200))
                gradient.setColorAt(1, self._color_mid)
            else:
                gradient.setColorAt(0, self._color_mid)
                gradient.setColorAt(1, self._color_high)

            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.PenStyle.NoPen)

            # Draw bar with slight rounded corners
            painter.drawRoundedRect(QRectF(x, y, bar_width, bar_h), 2, 2)

            # Glow effect (subtle wider bar behind)
            if intensity > 0.3:
                glow_color = QColor(212, 160, 23, int(40 * intensity))
                painter.setBrush(QBrush(glow_color))
                painter.drawRoundedRect(
                    QRectF(x - 1, y + 2, bar_width + 2, bar_h - 2), 2, 2
                )

            # Peak indicator dot
            peak_y = base_y - self._peak_bars[i] * bar_area_h
            if self._peak_bars[i] > 0.05:
                painter.setBrush(QBrush(self._peak_color))
                painter.drawRoundedRect(
                    QRectF(x, peak_y - 2, bar_width, 3), 1, 1
                )

        # Draw subtle reflection
        painter.setOpacity(0.08)
        for i in range(NUM_BARS):
            bar_h = self._smoothed_bars[i] * bar_area_h * 0.3
            x = margin + i * bar_gap + (bar_gap - bar_width) / 2
            y = base_y

            if bar_h < 1:
                continue

            gradient = QLinearGradient(QPointF(x, y), QPointF(x, y + bar_h))
            gradient.setColorAt(0, self._color_low)
            gradient.setColorAt(1, QColor(0, 0, 0, 0))
            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(x, y, bar_width, bar_h), 2, 2)

        painter.end()


class VisualizerWindow(QWidget):
    """Standalone visualizer window."""

    def __init__(self, player, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⛧ RADIO2K — Visualizer")
        self.setMinimumSize(700, 350)
        self.resize(800, 400)
        self.setStyleSheet("background-color: #080808;")

        self._player = player
        self._loaded = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QLabel("  ⛧ VISUALIZER")
        header.setStyleSheet("""
            color: #d4a017;
            font-size: 14px;
            font-weight: bold;
            letter-spacing: 2px;
            padding: 8px 12px;
            background: #0c0c0c;
            border-bottom: 1px solid #1a1a1a;
        """)
        layout.addWidget(header)

        # Visualizer canvas
        self.canvas = VisualizerWidget()
        layout.addWidget(self.canvas, 1)

        # Update timer (60 fps)
        self._timer = QTimer(self)
        self._timer.setInterval(33)  # ~30fps to stay nonlaggy
        self._timer.timeout.connect(self._update_frame)

    def load_track(self, filepath: str):
        """Load audio data for visualization."""
        self.canvas.load_audio(filepath)
        self._loaded = True

    def showEvent(self, event):
        """Start rendering when window becomes visible."""
        super().showEvent(event)
        if self._player.current_file:
            self.load_track(self._player.current_file)
        self._timer.start()

    def hideEvent(self, event):
        """Stop rendering and free memory when hidden."""
        super().hideEvent(event)
        self._timer.stop()

    def closeEvent(self, event):
        """Free audio data when window is closed."""
        self._timer.stop()
        self.canvas.unload_audio()
        self._loaded = False
        super().closeEvent(event)

    def _update_frame(self):
        """Called by timer to update the visualizer."""
        if not self.isVisible():
            return
        pos = self._player.get_position_ms()
        self.canvas.update_frame(pos)

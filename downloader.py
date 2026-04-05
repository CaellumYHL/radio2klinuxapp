import subprocess
import os
from PyQt6.QtCore import QThread, pyqtSignal

class YTDownloaderThread(QThread):
    """Background thread to download YouTube audio using yt-dlp outside the main GUI thread."""
    success = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, url: str, output_dir: str):
        super().__init__()
        self.url = url
        self.output_dir = output_dir

    def run(self):
        try:
            # -f bestaudio -x --audio-format mp3 --audio-quality 0 --embed-thumbnail --add-metadata
            # Also output file naming template: -o "{output_dir}/%(title)s.%(ext)s"
            command = [
                "yt-dlp",
                "-f", "bestaudio",
                "-x",
                "--audio-format", "mp3",
                "--audio-quality", "0",
                "--embed-thumbnail",
                "--add-metadata",
                "--js-runtimes", "node",
                "--remote-components", "ejs:github",
                "--cookies-from-browser", "firefox",
                "-o", os.path.join(self.output_dir, "%(title)s.%(ext)s"),
                self.url
            ]

            process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False
            )

            if process.returncode == 0:
                self.success.emit()
            else:
                self.error.emit(process.stderr.strip() or "Unknown error occurred during yt-dlp execution.")
                
        except FileNotFoundError:
            self.error.emit("yt-dlp not found. Please install it with 'pip install yt-dlp' or from your system package manager.")
        except Exception as e:
            self.error.emit(str(e))

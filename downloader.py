import subprocess
import os
import sys
import shutil
import glob
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
            # yt-dlp's JS challenge solver requires Node.js v20+ (for --experimental-permission).
            # Always prefer NVM-managed versions (which are newer) over the system node (may be v18).
            nvm_versions = glob.glob(os.path.expanduser("~/.nvm/versions/node/*/bin/node"))
            if nvm_versions:
                # Sort by version number and take the latest
                node_path = sorted(nvm_versions, key=lambda p: [int(x) for x in p.split("/node/v")[1].split("/")[0].split(".")])[-1]
            else:
                node_path = shutil.which("node")

            # -f bestaudio -x --audio-format mp3 --audio-quality 0 --embed-thumbnail --add-metadata
            # Also output file naming template: -o "{output_dir}/%(title)s.%(ext)s"
            command = [
                # Use the venv's yt-dlp, not whatever is on PATH
                os.path.join(os.path.dirname(sys.executable), "yt-dlp"),
                "-f", "bestaudio",
                "-x",
                "--audio-format", "mp3",
                "--audio-quality", "0",
                "--embed-thumbnail",
                "--add-metadata",
                "--js-runtimes", f"node:{node_path}" if node_path else "node",
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

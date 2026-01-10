"""
Settings management for EXR Toolkit.

Handles persistent storage of user preferences in settings.ini.
"""

from configparser import ConfigParser
from pathlib import Path
from typing import Optional


class Settings:
    """Manages application settings via settings.ini."""

    # Settings file location (project root)
    SETTINGS_FILE = Path(__file__).parent.parent.parent / "settings.ini"

    # Section and keys
    SECTION = "preferences"
    KEY_INPUT_DIR = "last_input_dir"
    KEY_OUTPUT_DIR = "last_output_dir"
    KEY_COMPRESSION = "exr_compression"
    KEY_FRAME_POLICY = "frame_policy"

    def __init__(self):
        """Initialize settings from file or create defaults."""
        self.config = ConfigParser()
        self._load()

    def _load(self) -> None:
        """Load settings from file or create defaults."""
        if self.SETTINGS_FILE.exists():
            self.config.read(self.SETTINGS_FILE)
        else:
            # Create default section
            self.config.add_section(self.SECTION)
            self.config.set(self.SECTION, self.KEY_INPUT_DIR, "")
            self.config.set(self.SECTION, self.KEY_OUTPUT_DIR, "")
            self.config.set(self.SECTION, self.KEY_COMPRESSION, "zip")
            self.config.set(self.SECTION, self.KEY_FRAME_POLICY, "STOP_AT_SHORTEST")
            self._save()

    def _save(self) -> None:
        """Save settings to file."""
        self.SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(self.SETTINGS_FILE, "w") as f:
            self.config.write(f)

    def get_input_dir(self) -> Optional[str]:
        """Get last input directory."""
        try:
            val = self.config.get(self.SECTION, self.KEY_INPUT_DIR)
            return val if val else None
        except:
            return None

    def set_input_dir(self, path: str) -> None:
        """Set and save last input directory."""
        if not self.config.has_section(self.SECTION):
            self.config.add_section(self.SECTION)
        self.config.set(self.SECTION, self.KEY_INPUT_DIR, path)
        self._save()

    def get_output_dir(self) -> Optional[str]:
        """Get last output directory."""
        try:
            val = self.config.get(self.SECTION, self.KEY_OUTPUT_DIR)
            return val if val else None
        except:
            return None

    def set_output_dir(self, path: str) -> None:
        """Set and save last output directory."""
        if not self.config.has_section(self.SECTION):
            self.config.add_section(self.SECTION)
        self.config.set(self.SECTION, self.KEY_OUTPUT_DIR, path)
        self._save()

    def get_compression(self) -> str:
        """Get last compression setting (default: 'zip')."""
        try:
            return self.config.get(self.SECTION, self.KEY_COMPRESSION)
        except:
            return "zip"

    def set_compression(self, compression: str) -> None:
        """Set and save compression setting."""
        if not self.config.has_section(self.SECTION):
            self.config.add_section(self.SECTION)
        self.config.set(self.SECTION, self.KEY_COMPRESSION, compression)
        self._save()

    def get_frame_policy(self) -> str:
        """Get last frame policy setting (default: 'STOP_AT_SHORTEST')."""
        try:
            return self.config.get(self.SECTION, self.KEY_FRAME_POLICY)
        except:
            return "STOP_AT_SHORTEST"

    def set_frame_policy(self, policy: str) -> None:
        """Set and save frame policy setting."""
        if not self.config.has_section(self.SECTION):
            self.config.add_section(self.SECTION)
        self.config.set(self.SECTION, self.KEY_FRAME_POLICY, policy)
        self._save()
